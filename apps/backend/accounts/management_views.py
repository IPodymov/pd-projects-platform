from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from common.api import RevisionSerializer, GuardedModelViewSet
from common.access import institution_ids
from common.services import audit
from institutions.models import Classroom, StudentMembership
from institutions.views import MembershipSerializer, StaffSerializer
from courses.models import Course, Enrollment
from courses.views import EnrollmentSerializer
from projects.models import Project
from projects.views import ProjectSerializer
from .models import User
from .views import ProfileUpdateSerializer
from . import management


class AccountAdminPermission(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.is_active
            and (
                request.user.is_superuser
                or institution_ids(request.user, ["admin"]).exists()
            )
        )


class ManagedUserSerializer(RevisionSerializer):
    memberships = serializers.SerializerMethodField()
    enrollments = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()
    staff_assignments = serializers.SerializerMethodField()
    name = serializers.CharField(source="get_full_name", read_only=True)

    def institutions(self):
        return institution_ids(self.context["request"].user, ["admin"])

    def get_memberships(self, obj) -> list[dict]:
        qs = obj.studentmembership_set.filter(
            classroom__institution_id__in=self.institutions()
        ).select_related("classroom")
        return MembershipSerializer(qs, many=True).data

    def get_enrollments(self, obj) -> list[dict]:
        qs = Enrollment.objects.filter(
            user=obj, course__institution_id__in=self.institutions()
        ).select_related("course", "user")
        return EnrollmentSerializer(qs, many=True).data

    def get_projects(self, obj) -> list[dict]:
        return ProjectSerializer(
            obj.project_set.filter(classroom__institution_id__in=self.institutions()),
            many=True,
        ).data

    def get_staff_assignments(self, obj) -> list[dict]:
        return StaffSerializer(
            obj.staffassignment_set.filter(institution_id__in=self.institutions()),
            many=True,
        ).data

    def validate_date_of_birth(self, value):
        return ProfileUpdateSerializer().validate_date_of_birth(value)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "display_name",
            "date_of_birth",
            "is_active",
            "email_verified_at",
            "date_joined",
            "memberships",
            "enrollments",
            "projects",
            "staff_assignments",
        ]
        read_only_fields = ["id", "email", "name", "email_verified_at", "date_joined"]


class ClassAssignmentInput(serializers.Serializer):
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all())
    membership = serializers.PrimaryKeyRelatedField(
        queryset=StudentMembership.objects.all(), required=False, allow_null=True
    )


class StudentAttachInput(serializers.Serializer):
    email = serializers.EmailField()
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all())


class CourseAssignmentInput(serializers.Serializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all())


class ProjectAssignmentInput(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    role = serializers.ChoiceField(choices=["member", "leader"], default="member")


class NewUserProjectInput(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    classroom = serializers.PrimaryKeyRelatedField(queryset=Classroom.objects.all())


class ManagedUserViewSet(GuardedModelViewSet):
    permission_classes = [AccountAdminPermission]
    serializer_class = ManagedUserSerializer
    queryset = User.objects.none()
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        qs = management.users_for(self.request.user).order_by("email")
        search = self.request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q

            qs = qs.filter(
                Q(email__icontains=search) | Q(display_name__icontains=search)
            )
        return qs

    @extend_schema(exclude=True)
    def create(self, request, *args, **kwargs):
        raise ValidationError(
            "Используйте регистрацию или добавление зарегистрированного ученика"
        )

    def perform_update(self, s):
        user = s.instance
        management.require_managed_user(self.request.user, user)
        if "is_active" in s.validated_data:
            if not self.request.user.is_superuser:
                raise PermissionDenied(
                    "Отключать учётные записи может только администратор платформы"
                )
            if not s.validated_data["is_active"] and (
                user.is_superuser or user.pk == self.request.user.pk
            ):
                raise ValidationError(
                    "Учётную запись администратора платформы нельзя отключить"
                )
        s.save()
        audit(
            self.request.user,
            "account.admin_updated",
            user,
            details={"fields": list(s.validated_data)},
        )

    def result(self, user):
        return Response(self.get_serializer(user).data)

    @extend_schema(request=StudentAttachInput, responses=ManagedUserSerializer)
    @action(detail=False, methods=["post"])
    def add_student(self, request):
        s = StudentAttachInput(data=request.data)
        s.is_valid(raise_exception=True)
        return self.result(
            management.add_registered_student(request.user, **s.validated_data)
        )

    @extend_schema(request=ClassAssignmentInput, responses=ManagedUserSerializer)
    @action(detail=True, methods=["post"])
    def set_class(self, request, pk=None):
        s = ClassAssignmentInput(data=request.data)
        s.is_valid(raise_exception=True)
        return self.result(
            management.change_class(
                request.user,
                self.get_object(),
                **s.validated_data,
                expected=request.headers.get("If-Match"),
            )
        )

    @extend_schema(request=CourseAssignmentInput, responses=ManagedUserSerializer)
    @action(detail=True, methods=["post"])
    def add_course(self, request, pk=None):
        s = CourseAssignmentInput(data=request.data)
        s.is_valid(raise_exception=True)
        return self.result(
            management.add_course(
                request.user,
                self.get_object(),
                **s.validated_data,
                expected=request.headers.get("If-Match"),
            )
        )

    @extend_schema(request=ProjectAssignmentInput, responses=ManagedUserSerializer)
    @action(detail=True, methods=["post"])
    def add_project(self, request, pk=None):
        s = ProjectAssignmentInput(data=request.data)
        s.is_valid(raise_exception=True)
        return self.result(
            management.add_project(
                request.user,
                self.get_object(),
                **s.validated_data,
                expected=request.headers.get("If-Match"),
            )
        )

    @extend_schema(request=NewUserProjectInput, responses=ManagedUserSerializer)
    @action(detail=True, methods=["post"])
    def create_project(self, request, pk=None):
        s = NewUserProjectInput(data=request.data)
        s.is_valid(raise_exception=True)
        return self.result(
            management.create_project(
                request.user,
                self.get_object(),
                s.validated_data,
                expected=request.headers.get("If-Match"),
            )
        )
