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

    class Meta:
        model = Publication
        fields = [
            "id",
            "slug",
            "title",
            "body",
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


class PublicationViewSet(MaterialViewSet):
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
