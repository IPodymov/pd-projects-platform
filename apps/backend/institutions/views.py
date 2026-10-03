from common.api import RevisionReadOnlyViewSet, RevisionSerializer, GuardedModelViewSet
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from django.db import transaction
from . import services
from rest_framework.exceptions import PermissionDenied, ValidationError
from common.access import institution_ids, classrooms, require_institution
from common.services import audit
from .models import (
    Institution,
    Classroom,
    StaffAssignment,
    TeachingAssignment,
    StudentMembership,
)


class InstitutionSerializer(RevisionSerializer):
    class Meta:
        model = Institution
        fields = ["id", "name", "kind"]


class ClassroomSerializer(RevisionSerializer):
    institution_name = serializers.CharField(source="institution.name", read_only=True)

    class Meta:
        model = Classroom
        fields = ["id", "name", "academic_year", "institution", "institution_name"]


class StaffSerializer(RevisionSerializer):
    name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = StaffAssignment
        fields = ["id", "user", "name", "institution", "role", "active"]
        read_only_fields = fields


class TeachingSerializer(RevisionSerializer):
    class Meta:
        model = TeachingAssignment
        fields = ["id", "staff", "classroom", "active"]
        read_only_fields = ["active"]
        validators = []


class MembershipSerializer(RevisionSerializer):
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = StudentMembership
        fields = ["id", "user", "name", "email", "classroom", "started_at", "ended_at"]
        read_only_fields = fields


class InstitutionViewSet(GuardedModelViewSet):
    queryset = InstitutionSerializer.Meta.model.objects.none()
    serializer_class = InstitutionSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        u = self.request.user
        return Institution.objects.filter(
            id__in=set(institution_ids(u))
            | set(classrooms(u).values_list("institution_id", flat=True))
        )

    def perform_create(self, s):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Учреждения создаёт администратор платформы")
        obj = s.save()
        audit(self.request.user, "institution.created", obj, obj)

    def perform_update(self, s):
        require_institution(self.request.user, s.instance, ["admin"])
        obj = s.save()
        audit(self.request.user, "institution.changed", obj, obj)


class ClassroomViewSet(GuardedModelViewSet):
    queryset = ClassroomSerializer.Meta.model.objects.none()
    serializer_class = ClassroomSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return classrooms(self.request.user)

    def perform_create(self, s):
        inst = s.validated_data["institution"]
        require_institution(self.request.user, inst, ["admin"])
        obj = s.save()
        audit(self.request.user, "class.created", obj, inst)

    def perform_update(self, s):
        require_institution(self.request.user, s.instance.institution, ["admin"])
        if (
            "institution" in s.validated_data
            and s.validated_data["institution"] != s.instance.institution
        ):
            raise ValidationError(
                "Перемещение класса запрещено; создайте класс нового учебного года"
            )
        obj = s.save()
        audit(self.request.user, "class.changed", obj, obj.institution)


class ActiveSerializer(serializers.Serializer):
    active = serializers.BooleanField()


class TransferSerializer(serializers.Serializer):
    classroom = serializers.UUIDField()


class StaffViewSet(RevisionReadOnlyViewSet):
    queryset = StaffSerializer.Meta.model.objects.none()
    serializer_class = StaffSerializer

    def get_queryset(self):
        from django.db.models import Q

        return StaffAssignment.objects.filter(
            Q(
                institution_id__in=institution_ids(
                    self.request.user, ["admin", "curator"]
                )
            )
            | Q(teachingassignment__classroom__in=classrooms(self.request.user, True))
            | Q(user=self.request.user)
        ).distinct()

    @extend_schema(request=ActiveSerializer, responses=StaffSerializer)
    @action(detail=True, methods=["post"])
    def set_active(self, request, pk=None):
        data = ActiveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(
            self.get_serializer(
                services.set_staff_active(
                    request.user,
                    self.get_object(),
                    data.validated_data["active"],
                    request.headers.get("If-Match"),
                )
            ).data
        )


class TeachingViewSet(GuardedModelViewSet):
    queryset = TeachingSerializer.Meta.model.objects.none()
    serializer_class = TeachingSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return TeachingAssignment.objects.filter(
            classroom__in=classrooms(self.request.user, True)
        )

    def perform_create(self, s):
        staff = s.validated_data["staff"]
        cl = s.validated_data["classroom"]
        require_institution(self.request.user, cl.institution, ["admin"])
        if (
            staff.institution_id != cl.institution_id
            or staff.role != "teacher"
            or not staff.active
        ):
            raise ValidationError("Требуется активный преподаватель этого учреждения")
        with transaction.atomic():
            staff = StaffAssignment.objects.select_for_update().get(pk=staff.pk)
            if not staff.active:
                raise ValidationError("Назначение преподавателя завершено")
            obj, _ = TeachingAssignment.objects.get_or_create(staff=staff, classroom=cl)
            if not obj.active:
                obj.active = True
                obj.save()
            s.instance = obj
            audit(self.request.user, "teacher.assigned", obj, cl.institution)

    @extend_schema(request=ActiveSerializer, responses=TeachingSerializer)
    @action(detail=True, methods=["post"])
    def set_active(self, request, pk=None):
        data = ActiveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(
            self.get_serializer(
                services.set_teaching_active(
                    request.user,
                    self.get_object(),
                    data.validated_data["active"],
                    request.headers.get("If-Match"),
                )
            ).data
        )


class MembershipViewSet(RevisionReadOnlyViewSet):
    queryset = MembershipSerializer.Meta.model.objects.none()
    serializer_class = MembershipSerializer

    def get_queryset(self):
        from django.db.models import Q

        qs = StudentMembership.objects.filter(
            Q(classroom__in=classrooms(self.request.user, True))
            | Q(user=self.request.user)
        ).distinct()
        cl = self.request.query_params.get("classroom")
        return qs.filter(classroom_id=cl) if cl else qs

    @extend_schema(request=TransferSerializer, responses=MembershipSerializer)
    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        data = TransferSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        target = get_object_or_404(
            classrooms(request.user, True), pk=data.validated_data["classroom"]
        )
        return Response(
            self.get_serializer(
                services.transfer_student(
                    request.user,
                    self.get_object(),
                    target,
                    request.headers.get("If-Match"),
                )
            ).data
        )
