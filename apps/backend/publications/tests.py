from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from common.models import SeedReceipt
from .models import Topic, Publication
from .seed import export_seed, validate_seed, import_seed, checksum


class SeedTests(TestCase):
    def seed(self, materials=False):
        records = [
            {
                "model": "publications.topic",
                "key": "engineering",
                "fields": {"title": "Инженерия"},
            }
        ]
        if materials:
            records.append(
                {
                    "model": "publications.publication",
                    "key": "guide",
                    "fields": {
                        "title": "Материал",
                        "body": "Утверждено редактором",
                        "topic": "engineering",
                        "published": True,
                        "approved_for_production": True,
                        "is_demo": False,
                    },
                }
            )
        payload = {"format_version": 1, "records": records}
        return {**payload, "checksum": checksum(payload)}

    def rehash(self, seed):
        seed["checksum"] = checksum({k: seed[k] for k in ["format_version", "records"]})
        return seed

    def test_default_allowlist_and_explicit_material_filter(self):
        topic = Topic.objects.create(code="engineering", title="Инженерия")
        for slug, approved, demo in [
            ("ok", True, False),
            ("test", True, True),
            ("draft", False, False),
        ]:
            Publication.objects.create(
                slug=slug,
                title="X",
                body="X",
                topic=topic,
                published=True,
                approved_for_production=approved,
                is_demo=demo,
            )
        self.assertEqual(len(export_seed()["records"]), 1)
        records = export_seed(True)["records"]
        self.assertEqual(
            [r["key"] for r in records if r["model"] == "publications.publication"],
            ["ok"],
        )

    def test_unknown_model_field_and_demo_rejected(self):
        for change in ["model", "field", "demo", "unapproved"]:
            seed = self.seed(True)
            if change == "model":
                seed["records"][1]["model"] = "accounts.user"
            if change == "field":
                seed["records"][1]["fields"]["password"] = "secret"
            if change == "demo":
                seed["records"][1]["fields"]["is_demo"] = True
            if change == "unapproved":
                seed["records"][1]["fields"]["approved_for_production"] = False
            with self.assertRaises(ValidationError):
                validate_seed(self.rehash(seed))

    def test_closed_dependency_and_checksum(self):
        seed = self.seed(True)
        seed["records"].pop(0)
        with self.assertRaises(ValidationError):
            validate_seed(self.rehash(seed))
        seed = self.seed()
        seed["checksum"] = "bad"
        with self.assertRaises(ValidationError):
            validate_seed(seed)

    def test_dryrun_and_idempotence(self):
        seed = self.seed(True)
        report = import_seed(seed)
        self.assertEqual(len(report["created"]), 2)
        self.assertFalse(Topic.objects.exists())
        self.assertFalse(SeedReceipt.objects.exists())
        import_seed(seed, False)
        report = import_seed(seed, False)
        self.assertEqual(len(report["skipped"]), 2)
        self.assertEqual(Publication.objects.count(), 1)

    def test_update_and_manual_conflict(self):
        seed = self.seed()
        import_seed(seed, False)
        seed["records"][0]["fields"]["title"] = "Новая инженерия"
        self.rehash(seed)
        self.assertEqual(len(import_seed(seed, False)["updated"]), 1)
        Topic.objects.filter(pk="engineering").update(title="Ручная правка")
        with self.assertRaises(ValidationError):
            import_seed(seed, False)
        self.assertEqual(Topic.objects.get().title, "Ручная правка")

    def test_transaction_rolls_back_all_records(self):
        with patch.object(
            Publication, "save", side_effect=RuntimeError("simulated DB failure")
        ):
            with self.assertRaises(RuntimeError):
                import_seed(self.seed(True), False)
        self.assertFalse(Topic.objects.exists())
        self.assertFalse(SeedReceipt.objects.exists())

    def test_existing_unmanaged_conflict_is_not_silent(self):
        Topic.objects.create(code="engineering", title="Ручной справочник")
        with self.assertRaises(ValidationError):
            import_seed(self.seed(), False)

    def test_offset_datetime_is_idempotent(self):
        seed = self.seed(True)
        seed["records"][1] = {
            "model": "publications.competition",
            "key": "future",
            "fields": {
                "title": "Конкурс",
                "requirements": "Требования",
                "deadline": "2026-12-01T12:00:00+03:00",
                "topic": "engineering",
                "published": True,
                "approved_for_production": True,
                "is_demo": False,
            },
        }
        self.rehash(seed)
        import_seed(seed, False)
        self.assertEqual(len(import_seed(seed, False)["skipped"]), 2)

    def test_unagreed_topic_rejected(self):
        seed = self.seed()
        seed["records"][0]["key"] = "test-topic"
        with self.assertRaises(ValidationError):
            validate_seed(self.rehash(seed))

    def test_private_and_archived_materials_are_never_exported(self):
        topic = Topic.objects.create(code="safe", title="Тема")
        Publication.objects.create(
            topic=topic,
            slug="private",
            title="Secret",
            body="Secret",
            published=True,
            approved_for_production=True,
            visibility="authenticated",
        )
        Publication.objects.create(
            topic=topic,
            slug="archive",
            title="Old",
            body="Old",
            published=True,
            approved_for_production=True,
            archived=True,
        )
        self.assertEqual(export_seed(True)["records"], [])


from common.testing import PlatformCase
from django.utils import timezone
from datetime import timedelta
from projects.models import Project, ProjectMember
from common.api import BusinessError
from .models import Competition, ApplicationTransition
from .services import create_application, transition_application, edit_application


class CompetitionWorkflowTests(PlatformCase):
    def test_application_revision_history_deadline_and_permissions(self):
        project = Project.objects.create(title="Прототип", classroom=self.classroom)
        ProjectMember.objects.create(project=project, user=self.student)
        competition = Competition.objects.create(
            topic=Topic.objects.create(code="robot", title="Роботы"),
            slug="robot",
            title="Роботы",
            requirements="Прототип",
            deadline=timezone.now() + timedelta(days=1),
            published=True,
        )
        application = create_application(
            self.student,
            {"competition": competition, "project": project, "text": "Первая версия"},
        )
        transition_application(self.student, application, "submitted")
        application.refresh_from_db()
        transition_application(
            self.admin, application, "revision", "Уточните требования"
        )
        application.refresh_from_db()
        edit_application(self.student, application, {"text": "Исправлено"})
        application.refresh_from_db()
        transition_application(self.student, application, "submitted")
        application.refresh_from_db()
        transition_application(self.admin, application, "accepted")
        self.assertEqual(
            ApplicationTransition.objects.filter(application=application).count(), 4
        )
        self.assertEqual(
            ApplicationTransition.objects.filter(application=application)
            .order_by("created_at")
            .first()
            .snapshot["text"],
            "Первая версия",
        )
        with self.assertRaises(BusinessError):
            edit_application(self.student, application, {"text": "Мутация"})
        competition.deadline = timezone.now() - timedelta(seconds=1)
        competition.save()
        with self.assertRaises(BusinessError):
            create_application(
                self.student,
                {"competition": competition, "project": project, "text": "Поздно"},
            )
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.get(
                f"/api/v1/competition-applications/{application.pk}/"
            ).status_code,
            404,
        )
