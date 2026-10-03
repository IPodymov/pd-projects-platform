import re
from common.api import RevisionReadOnlyViewSet, RevisionSerializer, GuardedModelViewSet
from common.access import project_access
from common.services import audit
from projects.views import projects_for
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from accounts.models import User
from .models import Repository, PullRequest, LearningReview, SyncJob
from . import services


class RepositorySerializer(RevisionSerializer):
    class Meta:
        model = Repository
        fields = ["id", "project", "provider", "owner", "name", "enabled"]
        read_only_fields = ["enabled"]

    def validate(self, data):
        for name in ("owner", "name"):
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", data.get(name, "")) or data[
                name
            ] in (".", ".."):
                raise serializers.ValidationError({name: "Неверный путь репозитория"})
        return data


class SyncSerializer(RevisionSerializer):
    class Meta:
        model = SyncJob
        fields = ["id", "repository", "status", "error_code", "created_at"]
        read_only_fields = fields


class RepositoryViewSet(GuardedModelViewSet):
    serializer_class = RepositorySerializer
    queryset = Repository.objects.none()
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Repository.objects.filter(project__in=projects_for(self.request.user))

    def perform_create(self, s):
        project_access(self.request.user, s.validated_data["project"], True)
        obj = s.save(enabled=self.request.user.is_superuser)
        audit(
            self.request.user,
            "repository.connected",
            obj,
            obj.project.classroom.institution,
        )

    @extend_schema(request=None, responses=RepositorySerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not request.user.is_superuser:
            raise PermissionDenied(
                "Платформа утверждает доступ серверного токена к проекту"
            )
        obj = self.get_object()
        obj.enabled = True
        obj.save()
        audit(
            request.user, "repository.approved", obj, obj.project.classroom.institution
        )
        return Response(RepositorySerializer(obj).data)

    @extend_schema(request=None, responses=SyncSerializer)
    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        return Response(
            SyncSerializer(services.request_sync(request.user, self.get_object())).data,
            status=202,
        )


class PullSerializer(RevisionSerializer):
    class Meta:
        model = PullRequest
        fields = [
            "id",
            "repository",
            "external_number",
            "title",
            "status",
            "url",
            "head_sha",
            "source_updated_at",
        ]
        read_only_fields = fields


class AssignSerializer(serializers.Serializer):
    reviewer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class LearningReviewSerializer(RevisionSerializer):
    stale = serializers.SerializerMethodField()

    def get_stale(self, obj) -> bool:
        return obj.revision != obj.pull_request.head_sha

    class Meta:
        model = LearningReview
        fields = [
            "id",
            "pull_request",
            "reviewer",
            "result",
            "remarks",
            "revision",
            "stale",
            "decided_at",
        ]
        read_only_fields = fields


class PullViewSet(RevisionReadOnlyViewSet):
    serializer_class = PullSerializer
    queryset = PullRequest.objects.none()

    def get_queryset(self):
        return PullRequest.objects.filter(
            repository__project__in=projects_for(self.request.user)
        )

    @extend_schema(request=AssignSerializer, responses=LearningReviewSerializer)
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        s = AssignSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(
            LearningReviewSerializer(
                services.assign_review(
                    request.user, self.get_object(), s.validated_data["reviewer"]
                )
            ).data
        )


class DecisionSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=["accepted", "revision"])
    remarks = serializers.CharField(allow_blank=True)


class ReviewViewSet(RevisionReadOnlyViewSet):
    serializer_class = LearningReviewSerializer
    queryset = LearningReview.objects.none()

    def get_queryset(self):
        return LearningReview.objects.filter(
            pull_request__repository__project__in=projects_for(self.request.user)
        )

    @extend_schema(request=DecisionSerializer, responses=LearningReviewSerializer)
    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        s = DecisionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(
            LearningReviewSerializer(
                services.decide_review(
                    request.user,
                    self.get_object(),
                    **s.validated_data,
                    expected=request.headers.get("If-Match"),
                )
            ).data
        )


class SyncViewSet(RevisionReadOnlyViewSet):
    serializer_class = SyncSerializer
    queryset = SyncJob.objects.none()

    def get_queryset(self):
        return SyncJob.objects.filter(
            repository__project__in=projects_for(self.request.user)
        )


class WebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=None, responses={202: None})
    def post(self, request, pk):
        repository = get_object_or_404(Repository, pk=pk)
        event, created = services.receive_webhook(
            repository, request.body, request.headers
        )
        return Response({"id": str(event.pk), "duplicate": not created}, status=202)
