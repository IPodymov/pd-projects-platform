from common.api import RevisionSerializer, GuardedModelViewSet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from common.access import classrooms, institution_ids
from institutions.models import Classroom
from .models import Invitation, Prospect, ImportBatch
from . import services


class InvitationSerializer(RevisionSerializer):
    class Meta:
        model = Invitation
        fields = [
            "id",
            "email",
            "institution",
            "classroom",
            "prospect",
            "role",
            "status",
            "expires_at",
        ]
        read_only_fields = ["id", "prospect", "status", "expires_at"]


class ProspectSerializer(RevisionSerializer):
    class Meta:
        model = Prospect
        fields = ["id", "full_name", "email", "classroom", "user"]
        read_only_fields = fields


class ImportSerializer(RevisionSerializer):
    class Meta:
        model = ImportBatch
        fields = ["id", "classroom", "rows", "errors", "applied_at", "expires_at"]
        read_only_fields = fields


class ImportUploadSerializer(serializers.Serializer):
    classroom = serializers.UUIDField()
    file = serializers.FileField()


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)


class AcceptSerializer(TokenSerializer):
    code = serializers.RegexField(r"^\d{6}$")
    password = serializers.CharField(required=False, default="", write_only=True)


class EmailCorrectionSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResultSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ImportResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    skipped = serializers.IntegerField()


class InvitationViewSet(GuardedModelViewSet):
    queryset = InvitationSerializer.Meta.model.objects.none()
    serializer_class = InvitationSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        from django.db.models import Q

        services.expire()
        return Invitation.objects.filter(
            Q(classroom__in=classrooms(self.request.user, True))
            | Q(
                institution_id__in=institution_ids(self.request.user, ["admin"]),
                classroom__isnull=True,
            )
        )

    def perform_create(self, s):
        d = s.validated_data
        s.instance = services.issue(
            self.request.user,
            d["institution"],
            d["email"],
            d["role"],
            d.get("classroom"),
        )

    @extend_schema(request=None, responses=InvitationSerializer)
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        return Response(
            InvitationSerializer(services.revoke(request.user, self.get_object())).data
        )

    @extend_schema(request=None, responses=InvitationSerializer)
    @action(detail=True, methods=["post"])
    def reissue(self, request, pk=None):
        from django.db import transaction

        with transaction.atomic():
            obj = self.get_object()
            services.revoke(request.user, obj)
            new = services.issue(
                request.user,
                obj.institution,
                obj.email,
                obj.role,
                obj.classroom,
                obj.prospect,
            )
        return Response(InvitationSerializer(new).data)


class ProspectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProspectSerializer.Meta.model.objects.none()
    serializer_class = ProspectSerializer

    def get_queryset(self):
        return Prospect.objects.filter(
            classroom__in=classrooms(self.request.user, True)
        )

    @extend_schema(request=EmailCorrectionSerializer, responses=InvitationSerializer)
    @action(detail=True, methods=["post"])
    def correct_email(self, request, pk=None):
        s = EmailCorrectionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(
            InvitationSerializer(
                services.correct_email(
                    request.user, self.get_object(), s.validated_data["email"]
                )
            ).data
        )


class ImportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ImportSerializer.Meta.model.objects.none()
    serializer_class = ImportSerializer

    def get_queryset(self):
        return ImportBatch.objects.filter(
            actor=self.request.user, classroom__in=classrooms(self.request.user, True)
        )

    @extend_schema(request=ImportUploadSerializer, responses=ImportSerializer)
    @action(
        detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser]
    )
    def preview(self, request):
        s = ImportUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        cl = get_object_or_404(Classroom, pk=s.validated_data["classroom"])
        return Response(
            ImportSerializer(
                services.preview_import(request.user, cl, s.validated_data["file"])
            ).data
        )

    @extend_schema(request=None, responses=ImportResultSerializer)
    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        return Response(services.apply_import(request.user, self.get_object()))


class RequestCodeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=TokenSerializer, responses=ResultSerializer)
    def post(self, request):
        s = TokenSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.request_code(s.validated_data["token"])
        return Response({"detail": "Код отправлен на почту из приглашения"})


class AcceptView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=AcceptSerializer, responses=ResultSerializer)
    def post(self, request):
        s = AcceptSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.accept(current_user=request.user, **s.validated_data)
        return Response(
            {"detail": "Приглашение принято. Войдите с вашей почтой и паролем."}
        )


class ExportView(APIView):
    @extend_schema(
        responses={
            (
                200,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ): bytes
        }
    )
    def get(self, request, pk):
        cl = get_object_or_404(Classroom, pk=pk)
        response = HttpResponse(
            services.export_class(request.user, cl),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="invitations.xlsx"'
        response["Cache-Control"] = "private, no-store"
        return response


class TemplateView(APIView):
    @extend_schema(responses={(200, "text/csv"): bytes})
    def get(self, request):
        response = HttpResponse(
            "\ufeffФИО,email\n", content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="students-template.csv"'
        return response
