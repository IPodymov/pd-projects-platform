from common.api import RevisionSerializer, GuardedModelViewSet
from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from projects.views import projects_for
from .models import (
    Publication,
    Competition,
    Topic,
    CompetitionApplication,
    ApplicationTransition,
)
from . import services


class PublicationSerializer(RevisionSerializer):
    status = serializers.CharField(read_only=True)
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)

    class Meta:
        model = Publication
        read_only_fields = ["author"]
        fields = [
            "id",
            "slug",
            "title",
            "body",
            "lead",
            "author",
            "author_name",
            "created_at",
            "topic",
            "visibility",
            "status",
            "updated_at",
        ]


class CompetitionSerializer(RevisionSerializer):
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Competition
        fields = [
            "id",
            "slug",
            "title",
            "requirements",
            "deadline",
            "topic",
            "visibility",
            "status",
        ]


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["code", "title"]


class MaterialTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["published", "archived"])


class MaterialViewSet(GuardedModelViewSet):
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = self.serializer_class.Meta.model.objects.all()
        if self.request.user.is_superuser:
            return qs
        qs = qs.filter(published=True, archived=False)
        return (
            qs if self.request.user.is_authenticated else qs.filter(visibility="public")
        )

    def perform_create(self, s):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Только администратор платформы")
        s.save()

    def perform_update(self, s):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Только администратор платформы")
        if s.instance.status != "draft":
            raise ValidationError("Редактировать можно только черновик")
        s.save()

    @extend_schema(request=MaterialTransitionSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        s = MaterialTransitionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        obj = services.publish_material(
            request.user,
            self.get_object(),
            s.validated_data["status"],
            request.headers.get("If-Match"),
        )
        return Response(self.get_serializer(obj).data)


class BlogImageUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class BlogImageResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    path = serializers.CharField()


class PublicationAttachmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    filename = serializers.CharField()
    size = serializers.IntegerField()


class PublicationAttachmentRemoveSerializer(serializers.Serializer):
    attachment = serializers.UUIDField()


class PublicationViewSet(MaterialViewSet):
    def get_queryset(self):
        from django.db.models import Q

        qs = Publication.objects.select_related("author")
        if self.request.user.is_superuser:
            return qs
        visible = Q(published=True, archived=False)
        if not self.request.user.is_authenticated:
            return qs.filter(visible, visibility="public")
        return qs.filter(visible | Q(author=self.request.user))

    def perform_create(self, s):
        services.require_author(self.request.user)
        s.save(author=self.request.user)

    def perform_update(self, s):
        services.require_author(self.request.user, s.instance)
        if s.instance.status != "draft":
            raise ValidationError("Редактировать можно только черновик")
        s.save()

    @extend_schema(
        request=BlogImageUploadSerializer, responses=BlogImageResultSerializer
    )
    @action(detail=True, methods=["post"])
    def upload_image(self, request, pk=None):
        import io, uuid, warnings
        from PIL import Image, UnidentifiedImageError
        from django.core.files.base import ContentFile
        from django.db import transaction
        from .models import PublicationImage

        with transaction.atomic():
            obj = Publication.objects.select_for_update().get(pk=self.get_object().pk)
            services.require_author(request.user, obj)
            if obj.status != "draft":
                raise ValidationError("Изображения добавляются только в черновик")
            s = BlogImageUploadSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            upload = s.validated_data["file"]
            if upload.size > 5 * 1024 * 1024:
                raise ValidationError({"file": "Изображение — до 5 МБ"})
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    picture = Image.open(io.BytesIO(upload.read(5 * 1024 * 1024 + 1)))
                    if (
                        picture.format not in {"PNG", "JPEG"}
                        or picture.width * picture.height > 20_000_000
                    ):
                        raise ValidationError(
                            {"file": "PNG или JPEG до 20 мегапикселей"}
                        )
                    picture.load()
                    # Re-encode pixels to remove metadata and embedded payloads.
                    output = io.BytesIO()
                    picture.convert("RGB").save(output, format="JPEG", quality=90)
            except (
                UnidentifiedImageError,
                OSError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
            ):
                raise ValidationError({"file": "Некорректное изображение"})
            image = PublicationImage(publication=obj, content_type="image/jpeg")
            image.file.save(
                str(uuid.uuid4()) + ".jpg", ContentFile(output.getvalue()), save=False
            )
            image.save()
        return Response(
            {"id": image.pk, "path": f"publications/{obj.pk}/image/?image={image.pk}"},
            status=201,
        )

    @extend_schema(responses={(200, "image/jpeg"): bytes})
    @action(detail=True, methods=["get"])
    def image(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        from django.http import FileResponse
        from .models import PublicationImage

        image = get_object_or_404(
            PublicationImage,
            publication=self.get_object(),
            pk=request.query_params.get("image"),
        )
        response = FileResponse(image.file.open("rb"), content_type=image.content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @extend_schema(responses=PublicationAttachmentSerializer(many=True))
    @action(detail=True, methods=["get"])
    def attachments(self, request, pk=None):
        return Response(
            PublicationAttachmentSerializer(
                self.get_object().attachments.filter(removed=False), many=True
            ).data
        )

    @extend_schema(
        request=BlogImageUploadSerializer, responses=PublicationAttachmentSerializer
    )
    @action(detail=True, methods=["post"])
    def upload_attachment(self, request, pk=None):
        import uuid
        from pathlib import Path
        from django.db import transaction
        from django.core.files.base import ContentFile
        from common.uploads import validate_attachment
        from .models import PublicationAttachment

        with transaction.atomic():
            obj = Publication.objects.select_for_update().get(pk=self.get_object().pk)
            services.require_author(request.user, obj)
            if obj.status != "draft":
                raise ValidationError("Файлы добавляются только в черновик")
            if obj.attachments.filter(removed=False).count() >= 10:
                raise ValidationError("Не более 10 материалов на статью")
            s = BlogImageUploadSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            upload = s.validated_data["file"]
            content, extension, _ = validate_attachment(upload)
            attachment = PublicationAttachment(
                publication=obj,
                filename=Path(upload.name).name[:200],
                size=len(content),
            )
            attachment.file.save(
                str(uuid.uuid4()) + extension, ContentFile(content), save=False
            )
            attachment.save()
        return Response(PublicationAttachmentSerializer(attachment).data, status=201)

    @extend_schema(request=PublicationAttachmentRemoveSerializer, responses=None)
    @action(detail=True, methods=["post"])
    def remove_attachment(self, request, pk=None):
        from django.db import transaction
        from django.shortcuts import get_object_or_404

        with transaction.atomic():
            obj = Publication.objects.select_for_update().get(pk=self.get_object().pk)
            services.require_author(request.user, obj)
            if obj.status != "draft":
                raise ValidationError("Материалы опубликованной статьи неизменяемы")
            s = PublicationAttachmentRemoveSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            attachment = get_object_or_404(
                obj.attachments, pk=s.validated_data["attachment"], removed=False
            )
            attachment.removed = True
            attachment.save(update_fields=["removed", "updated_at"])
        return Response(status=204)

    @extend_schema(responses={(200, "application/octet-stream"): bytes})
    @action(detail=True, methods=["get"])
    def attachment(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        from django.http import FileResponse

        attachment = get_object_or_404(
            self.get_object().attachments,
            pk=request.query_params.get("attachment"),
            removed=False,
        )
        response = FileResponse(
            attachment.file.open("rb"), as_attachment=True, filename=attachment.filename
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    serializer_class = PublicationSerializer
    queryset = Publication.objects.none()


class CompetitionViewSet(MaterialViewSet):
    serializer_class = CompetitionSerializer
    queryset = Competition.objects.none()


class TopicViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = TopicSerializer
    queryset = Topic.objects.all()


class ApplicationHistorySerializer(RevisionSerializer):
    class Meta:
        model = ApplicationTransition
        fields = [
            "id",
            "actor",
            "previous",
            "status",
            "feedback",
            "snapshot",
            "created_at",
        ]
        read_only_fields = fields


class ApplicationSerializer(RevisionSerializer):
    history = ApplicationHistorySerializer(many=True, read_only=True)

    class Meta:
        model = CompetitionApplication
        fields = ["id", "competition", "project", "author", "text", "status", "history"]
        read_only_fields = ["author", "status"]
        validators = []


class ApplicationTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["submitted", "revision", "accepted", "rejected", "cancelled"]
    )
    feedback = serializers.CharField(required=False, default="", allow_blank=True)


class ApplicationViewSet(GuardedModelViewSet):
    serializer_class = ApplicationSerializer
    queryset = CompetitionApplication.objects.none()
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return CompetitionApplication.objects.filter(
            project__in=projects_for(self.request.user)
        ).prefetch_related("history")

    def perform_create(self, s):
        s.instance = services.create_application(self.request.user, s.validated_data)

    def perform_update(self, s):
        s.instance = services.edit_application(
            self.request.user,
            s.instance,
            s.validated_data,
            self.request.headers.get("If-Match"),
        )

    @extend_schema(
        request=ApplicationTransitionSerializer, responses=ApplicationSerializer
    )
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        s = ApplicationTransitionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(
            ApplicationSerializer(
                services.transition_application(
                    request.user,
                    self.get_object(),
                    **s.validated_data,
                    expected=request.headers.get("If-Match"),
                )
            ).data
        )
