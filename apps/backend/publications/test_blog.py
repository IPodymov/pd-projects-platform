from common.testing import PlatformCase
from institutions.models import StaffAssignment
from .models import Publication, Topic


class CuratorBlogTests(PlatformCase):
    def test_curator_draft_author_publication_and_isolation(self):
        topic = Topic.objects.create(code="engineering", title="Инженерия")
        self.client.force_authenticate(self.curator)
        response = self.client.post(
            "/api/v1/publications/",
            {
                "slug": "article",
                "title": "Статья",
                "body": "## Опыт\nТекст",
                "lead": "Вступление",
                "topic": topic.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        pk, revision = response.data["id"], response.data["updated_at"]
        self.assertEqual(Publication.objects.get(pk=pk).author, self.curator)
        StaffAssignment.objects.create(
            user=self.stranger, institution=self.school, role="curator"
        )
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.get(f"/api/v1/publications/{pk}/").status_code, 404
        )
        self.client.force_authenticate(self.curator)
        response = self.client.post(
            f"/api/v1/publications/{pk}/transition/",
            {"status": "published"},
            format="json",
            HTTP_IF_MATCH=revision,
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(self.stranger)
        response = self.client.patch(
            f"/api/v1/publications/{pk}/",
            {"body": "Изменено"},
            format="json",
            HTTP_IF_MATCH=response.data["updated_at"],
        )
        self.assertEqual(response.status_code, 403)
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(f"/api/v1/publications/{pk}/").status_code, 200
        )

    def test_teacher_cannot_author_blog_or_forge_author(self):
        topic = Topic.objects.create(code="science", title="Наука")
        response = self.client.post(
            "/api/v1/publications/",
            {"slug": "bad", "title": "Статья", "body": "Текст", "topic": topic.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.client.force_authenticate(self.curator)
        response = self.client.post(
            "/api/v1/publications/",
            {
                "slug": "bad",
                "title": "Статья",
                "body": "Текст",
                "topic": topic.pk,
                "author": str(self.admin.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_images_follow_article_visibility_and_reject_fake_files(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(self.curator)
        topic = Topic.objects.create(code="images", title="Изображения")
        article = Publication.objects.create(
            author=self.curator, slug="images", title="Фото", body="Текст", topic=topic
        )
        path = f"/api/v1/publications/{article.pk}/upload_image/"
        response = self.client.post(
            path,
            {"file": SimpleUploadedFile("bad.png", b"<script>")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(buffer, format="PNG")
        response = self.client.post(
            path,
            {"file": SimpleUploadedFile("good.png", buffer.getvalue())},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        image_path = "/api/v1/" + response.data["path"]
        self.assertEqual(self.client.get(image_path).status_code, 200)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(image_path).status_code, 404)
        article.published = True
        article.save()
        self.assertEqual(self.client.get(image_path).status_code, 200)
        article.visibility = "authenticated"
        article.save()
        self.assertEqual(self.client.get(image_path).status_code, 404)

    def test_attachments_visibility_removal_and_published_immutability(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(self.curator)
        topic = Topic.objects.create(code="attachments", title="Материалы")
        article = Publication.objects.create(
            author=self.curator,
            slug="attachments",
            title="Материалы",
            body="Текст",
            topic=topic,
        )
        path = f"/api/v1/publications/{article.pk}/"
        response = self.client.post(
            path + "upload_attachment/",
            {"file": SimpleUploadedFile("notes.md", "# Заметки".encode())},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        attachment = response.data["id"]
        download = path + f"attachment/?attachment={attachment}"
        self.assertEqual(self.client.get(download).status_code, 200)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(download).status_code, 404)
        self.assertEqual(self.client.get(path + "attachments/").status_code, 404)
        article.published = True
        article.save()
        self.assertEqual(self.client.get(download).status_code, 200)
        self.client.force_authenticate(self.curator)
        self.assertEqual(
            self.client.post(
                path + "remove_attachment/", {"attachment": attachment}, format="json"
            ).status_code,
            400,
        )
        article.published = False
        article.save()
        response = self.client.post(
            path + "remove_attachment/", {"attachment": attachment}, format="json"
        )
        self.assertEqual(response.status_code, 204, response.data)
        self.assertEqual(self.client.get(download).status_code, 404)
        self.assertEqual(self.client.get(path + "attachments/").data, [])

    def test_attachments_reject_invalid_formats_and_limit_count(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import PublicationAttachment

        self.client.force_authenticate(self.curator)
        topic = Topic.objects.create(code="limited", title="Материалы")
        article = Publication.objects.create(
            author=self.curator,
            slug="limited",
            title="Статья",
            body="Текст",
            topic=topic,
        )
        path = f"/api/v1/publications/{article.pk}/upload_attachment/"
        response = self.client.post(
            path,
            {"file": SimpleUploadedFile("fake.pdf", b"not PDF")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        PublicationAttachment.objects.bulk_create(
            [
                PublicationAttachment(
                    publication=article, file="unused", filename=f"{i}.txt", size=1
                )
                for i in range(10)
            ]
        )
        response = self.client.post(
            path, {"file": SimpleUploadedFile("notes.txt", b"text")}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)
