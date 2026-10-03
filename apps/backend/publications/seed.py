"""Production transfer protocol. Deliberately unrelated to dumpdata."""

import hashlib, json
from datetime import timezone as utc_timezone
from django.core.exceptions import ValidationError
from django.db import transaction, connection
from django.utils.dateparse import parse_datetime
from common.models import SeedReceipt
from .models import Topic, Publication, Competition

FORMAT = 1
TECHNICAL_TOPICS = frozenset({"engineering", "robotics", "research"})
ALLOWLIST = {
    "publications.topic": {"model": Topic, "key": "code", "fields": ["title"]},
    "publications.publication": {
        "model": Publication,
        "key": "slug",
        "fields": [
            "title",
            "body",
            "topic",
            "published",
            "approved_for_production",
            "is_demo",
        ],
    },
    "publications.competition": {
        "model": Competition,
        "key": "slug",
        "fields": [
            "title",
            "requirements",
            "deadline",
            "topic",
            "published",
            "approved_for_production",
            "is_demo",
        ],
    },
}


def checksum(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def fields_of(obj, spec):
    result = {}
    for f in spec["fields"]:
        v = getattr(obj, f + "_id") if f == "topic" else getattr(obj, f)
        if hasattr(v, "isoformat"):
            v = v.astimezone(utc_timezone.utc).isoformat()
        result[f] = v
    return result


def fingerprint_fields(fields):
    fields = dict(fields)
    if "deadline" in fields:
        fields["deadline"] = (
            parse_datetime(fields["deadline"]).astimezone(utc_timezone.utc).isoformat()
        )
    return checksum(fields)


def export_seed(include_materials=False):
    records = []
    for label, spec in ALLOWLIST.items():
        qs = spec["model"].objects.all()
        if label == "publications.topic":
            qs = qs.filter(code__in=TECHNICAL_TOPICS)
        if label != "publications.topic":
            if not include_materials:
                continue
            qs = qs.filter(
                approved_for_production=True,
                is_demo=False,
                published=True,
                visibility="public",
                archived=False,
            )
        for obj in qs.order_by(spec["key"]):
            records.append(
                {
                    "model": label,
                    "key": getattr(obj, spec["key"]),
                    "fields": fields_of(obj, spec),
                }
            )
    payload = {"format_version": FORMAT, "records": records}
    return {**payload, "checksum": checksum(payload)}


def validate_seed(seed):
    if not isinstance(seed, dict) or set(seed) != {
        "format_version",
        "records",
        "checksum",
    }:
        raise ValidationError("Неверный конверт seed")
    if type(seed["format_version"]) is not int or seed["format_version"] != FORMAT:
        raise ValidationError("Неизвестная версия seed")
    payload = {k: seed[k] for k in ["format_version", "records"]}
    if not isinstance(seed["checksum"], str) or seed["checksum"] != checksum(payload):
        raise ValidationError("Контрольная сумма не совпадает")
    if not isinstance(seed["records"], list) or len(seed["records"]) > 10000:
        raise ValidationError("Некорректный список записей")
    seen = set()
    topics = set()
    for r in seed["records"]:
        if not isinstance(r, dict) or set(r) != {"model", "key", "fields"}:
            raise ValidationError("Неизвестные поля записи")
        spec = ALLOWLIST.get(r["model"])
        if not spec:
            raise ValidationError("Модель запрещена для production seed")
        if not isinstance(r["key"], str) or not r["key"] or len(r["key"]) > 50:
            raise ValidationError("Некорректный natural key")
        identity = (r["model"], r["key"])
        if identity in seen:
            raise ValidationError("Дубликат natural key")
        seen.add(identity)
        if not isinstance(r["fields"], dict) or set(r["fields"]) != set(spec["fields"]):
            raise ValidationError("Неверные или запрещённые поля")
        for f, v in r["fields"].items():
            if f in ("published", "approved_for_production", "is_demo"):
                if type(v) is not bool:
                    raise ValidationError("Требуется boolean")
            elif not isinstance(v, str):
                raise ValidationError("Требуется строка: " + f)
            field = spec["model"]._meta.get_field(f)
            if f != "topic":
                field.clean(v, None)
        spec["model"]._meta.get_field(spec["key"]).clean(r["key"], None)
        if r["model"] == "publications.topic":
            if r["key"] not in TECHNICAL_TOPICS:
                raise ValidationError("Справочник не входит в согласованный набор")
            topics.add(r["key"])
        else:
            fs = r["fields"]
            if (
                fs["approved_for_production"] is not True
                or fs["published"] is not True
                or fs["is_demo"] is not False
            ):
                raise ValidationError(
                    "Материал не утверждён для production или является demo"
                )
            if "deadline" in fs:
                value = parse_datetime(fs["deadline"])
                if not value or value.tzinfo is None:
                    raise ValidationError("Deadline должен содержать часовой пояс")
    # Closed dependency graph: never silently pull related local/production objects.
    for r in seed["records"]:
        if "topic" in r["fields"] and r["fields"]["topic"] not in topics:
            raise ValidationError("Связанный справочник отсутствует в seed")
    return seed


@transaction.atomic
def import_seed(seed, dry_run=True):
    validate_seed(seed)
    if connection.vendor == "postgresql":
        with connection.cursor() as c:
            c.execute("SELECT pg_advisory_xact_lock(%s)", [741923])
    report = {
        "created": [],
        "updated": [],
        "skipped": [],
        "conflicts": [],
        "dry_run": dry_run,
    }
    records = sorted(
        seed["records"], key=lambda r: 0 if r["model"] == "publications.topic" else 1
    )
    changes = []
    for r in records:
        spec = ALLOWLIST[r["model"]]
        key = r["model"] + ":" + r["key"]
        obj = (
            spec["model"]
            .objects.select_for_update()
            .filter(**{spec["key"]: r["key"]})
            .first()
        )
        if obj is not None and (
            getattr(obj, "visibility", "public") != "public"
            or getattr(obj, "archived", False)
        ):
            report["conflicts"].append(key)
            continue
        wanted = fingerprint_fields(r["fields"])
        receipt = SeedReceipt.objects.select_for_update().filter(pk=key).first()
        if obj is None:
            report["created"].append(key)
            changes.append((r, None, wanted))
        else:
            current = fingerprint_fields(fields_of(obj, spec))
            if current == wanted:
                report["skipped"].append(key)
            elif not receipt or receipt.fingerprint != current:
                report["conflicts"].append(key)
            else:
                report["updated"].append(key)
                changes.append((r, obj, wanted))
    if report["conflicts"]:
        raise ValidationError(
            "Конфликт ручных изменений: " + ", ".join(report["conflicts"])
        )
    if not dry_run:
        for r, obj, wanted in changes:
            spec = ALLOWLIST[r["model"]]
            fs = dict(r["fields"])
            if "topic" in fs:
                fs["topic_id"] = fs.pop("topic")
            if obj is None:
                obj = spec["model"](**{spec["key"]: r["key"]}, **fs)
            else:
                for f, v in fs.items():
                    setattr(obj, f, v)
            obj.full_clean()
            obj.save()
            SeedReceipt.objects.update_or_create(
                key=r["model"] + ":" + r["key"], defaults={"fingerprint": wanted}
            )
        for key in report["skipped"]:
            r = next(r for r in records if r["model"] + ":" + r["key"] == key)
            SeedReceipt.objects.get_or_create(
                key=key, defaults={"fingerprint": fingerprint_fields(r["fields"])}
            )
    return report
