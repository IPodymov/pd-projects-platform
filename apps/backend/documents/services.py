import hashlib, uuid, difflib
from pathlib import Path
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework.exceptions import ValidationError
from common.access import project_access
from common.services import audit
from crm.models import LearningActivity
from .models import Document, DocumentVersion, Comparison


@transaction.atomic
def upload_version(actor, document, upload, restored_from=None):
    project_access(actor, document.project)
    # Lock parent; serializes previous pointer even for concurrent uploads.
    document = Document.objects.select_for_update().get(pk=document.pk)
    from common.uploads import validate_attachment

    content, ext, text = validate_attachment(upload)
    previous = document.versions.order_by("-created_at").first()
    v = DocumentVersion(
        document=document,
        author=actor,
        previous=previous,
        restored_from=restored_from,
        filename=Path(upload.name).name[:200],
        checksum=hashlib.sha256(content).hexdigest(),
        size=len(content),
        text_content=text,
        extraction_status="done"
        if text or ext in {".txt", ".md", ".csv"}
        else "pending"
        if ext in {".docx", ".pptx"}
        else "unavailable",
    )
    v.file.save(str(uuid.uuid4()) + ext, ContentFile(content), save=False)
    v.save()
    LearningActivity.objects.create(
        actor=actor,
        classroom=document.project.classroom,
        kind="document.uploaded",
        target=str(v.pk),
    )
    audit(actor, "document.uploaded", v, document.project.classroom.institution)
    if v.extraction_status == "pending":
        from common.outbox import enqueue

        enqueue("extract", {"pk": str(v.pk)}, f"extract:{v.pk}")
    return v


def restore(actor, version):
    project_access(actor, version.document.project)
    with version.file.open("rb") as f:
        upload = ContentFile(f.read(), name=version.filename)
    return upload_version(actor, version.document, upload, version)


def compare(actor, old, new):
    project_access(actor, old.document.project)
    project_access(actor, new.document.project)
    if old.document_id != new.document_id:
        raise ValidationError("Версии разных документов")
    if "unavailable" in {old.extraction_status, new.extraction_status}:
        raise ValidationError(
            "Для PDF и изображений доступно скачивание, сравнение текста не поддерживается"
        )
    if old.extraction_status != "done" or new.extraction_status != "done":
        raise ValidationError("Извлечение текста ещё не завершено")
    # Structured text lines; frontend escapes content instead of rendering arbitrary HTML.
    if (
        max(len(old.text_content), len(new.text_content)) > 2_000_000
        or max(len(old.text_content.splitlines()), len(new.text_content.splitlines()))
        > 20000
    ):
        raise ValidationError("Документ слишком велик для детального сравнения")
    lines = []
    for line in difflib.unified_diff(
        old.text_content.splitlines(),
        new.text_content.splitlines(),
        fromfile=old.filename,
        tofile=new.filename,
        lineterm="",
    ):
        kind = "context"
        if line.startswith("@@"):
            kind = "hunk"
        elif line.startswith(("---", "+++")):
            kind = "header"
        elif line.startswith("+"):
            kind = "add"
        elif line.startswith("-"):
            kind = "delete"
        lines.append({"kind": kind, "text": line})
    deleted = []
    for entry in lines:
        entry["ranges"] = []
        if entry["kind"] == "delete":
            deleted.append(entry)
        elif entry["kind"] == "add" and deleted:
            previous = deleted.pop(0)
            left, right = previous["text"][1:2049], entry["text"][1:2049]
            for tag, a, b, c, d in difflib.SequenceMatcher(
                None, left, right
            ).get_opcodes():
                if tag != "equal":
                    if a != b:
                        previous["ranges"].append([a + 1, b + 1])
                    if c != d:
                        entry["ranges"].append([c + 1, d + 1])
        elif entry["kind"] not in ("add", "delete"):
            deleted = []
    return {"lines": lines, "comparison": "text", "visual_office_diff": False}


@transaction.atomic
def request_comparison(actor, old, new):
    project_access(actor, old.document.project)
    project_access(actor, new.document.project)
    if old.document_id != new.document_id:
        raise ValidationError("Версии разных документов")
    # Parent lock also serializes competing identical comparison requests.
    Document.objects.select_for_update().get(pk=old.document_id)
    obj, _ = Comparison.objects.get_or_create(
        old=old, new=new, defaults={"initiator": actor}
    )
    from common.outbox import enqueue

    if obj.status == "failed":
        obj.status = "queued"
        obj.error_code = ""
        obj.save()
    enqueue(
        "compare", {"pk": str(obj.pk)}, f"compare:{obj.pk}:{obj.updated_at.isoformat()}"
    )
    return obj
