from common.api import RevisionSerializer, GuardedModelViewSet
from django.http import FileResponse
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema
from common.access import project_access
from projects.views import projects_for
from .models import Document, DocumentVersion, Comparison
from .services import upload_version, restore, compare, request_comparison


class DocumentSerializer(RevisionSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "project"]


class VersionSerializer(RevisionSerializer):
    class Meta:
        model = DocumentVersion
        fields = [
            "id",
            "document",
            "filename",
            "checksum",
            "size",
            "author",
            "previous",
            "restored_from",
            "extraction_status",
            "created_at",
        ]
        read_only_fields = fields


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class CompareSerializer(serializers.Serializer):
    other = serializers.UUIDField()


class DiffLineSerializer(serializers.Serializer):
    kind = serializers.CharField()
    text = serializers.CharField()


class DiffSerializer(serializers.Serializer):
    lines = DiffLineSerializer(many=True)
    comparison = serializers.CharField()
    visual_office_diff = serializers.BooleanField()


class DocumentViewSet(GuardedModelViewSet):
    queryset = DocumentSerializer.Meta.model.objects.none()
    serializer_class = DocumentSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Document.objects.filter(project__in=projects_for(self.request.user))

    def perform_create(self, s):
        project_access(self.request.user, s.validated_data["project"])
        s.save()

    @extend_schema(request=UploadSerializer, responses=VersionSerializer)
    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request, pk=None):
        s = UploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(
            VersionSerializer(
                upload_version(
                    request.user, self.get_object(), s.validated_data["file"]
                )
            ).data,
            status=201,
        )


class ComparisonSerializer(RevisionSerializer):
    class Meta:
        model = Comparison
        fields = ["id", "old", "new", "status", "result", "error_code", "created_at"]
        read_only_fields = fields


class VersionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VersionSerializer.Meta.model.objects.none()
    serializer_class = VersionSerializer

    def get_queryset(self):
        q = DocumentVersion.objects.filter(
            document__project__in=projects_for(self.request.user)
        ).order_by("-created_at")
        doc = self.request.query_params.get("document")
        return q.filter(document_id=doc) if doc else q

    @extend_schema(responses={(200, "application/octet-stream"): bytes})
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        v = self.get_object()
        response = FileResponse(
            v.file.open("rb"), as_attachment=True, filename=v.filename
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @extend_schema(request=None, responses=VersionSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        return Response(
            VersionSerializer(restore(request.user, self.get_object())).data, status=201
        )

    @extend_schema(
        parameters=[], request=CompareSerializer, responses={202: ComparisonSerializer}
    )
    @action(detail=True, methods=["post"])
    def compare(self, request, pk=None):
        s = CompareSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        from django.shortcuts import get_object_or_404

        other = get_object_or_404(self.get_queryset(), pk=s.validated_data["other"])
        if request.path.startswith("/api/v1/"):
            return Response(
                ComparisonSerializer(
                    request_comparison(request.user, self.get_object(), other)
                ).data,
                status=202,
            )
        return Response(compare(request.user, self.get_object(), other))


class ComparisonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Comparison.objects.none()
    serializer_class = ComparisonSerializer

    def get_queryset(self):
        return Comparison.objects.filter(
            old__document__project__in=projects_for(self.request.user)
        )
