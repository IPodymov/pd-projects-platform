from common.api import RevisionSerializer, GuardedModelViewSet
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db.models import Q
from common.access import (
    institution_ids,
    classrooms,
    require_institution,
)
from .models import Course, Enrollment, Assignment, CourseSubmission
from . import services
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema


class CourseStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["published", "archived"])


class CourseSerializer(RevisionSerializer):
    class Meta:
        model = Course
        fields = ["id", "title", "description", "institution", "status"]
        read_only_fields = ["status"]


class EnrollmentSerializer(RevisionSerializer):
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    progress = serializers.SerializerMethodField()

    def get_progress(self, obj) -> int:
        return services.progress(obj)

    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "user",
            "course",
            "course_title",
            "user_name",
            "classroom",
            "status",
            "progress",
        ]
        read_only_fields = ["status"]
        validators = []


class CourseViewSet(GuardedModelViewSet):
    queryset = CourseSerializer.Meta.model.objects.none()
    serializer_class = CourseSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return (
            Course.objects.filter(
                institution_id__in=set(institution_ids(self.request.user))
                | set(
                    classrooms(self.request.user).values_list(
                        "institution_id", flat=True
                    )
                )
            )
            .filter(
                Q(status="published")
                | Q(institution_id__in=institution_ids(self.request.user))
                | Q(enrollment__user=self.request.user)
            )
            .distinct()
        )

    def perform_create(self, s):
        require_institution(self.request.user, s.validated_data["institution"])
        s.save()

    def perform_update(self, s):
        require_institution(self.request.user, s.instance.institution)
        if (
            s.validated_data.get("institution", s.instance.institution)
            != s.instance.institution
        ):
            raise ValidationError("Учреждение курса неизменяемо")
        s.save()

    @extend_schema(request=CourseStatusSerializer, responses=CourseSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        s = CourseStatusSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(
            CourseSerializer(
                services.change_course(
                    request.user,
                    self.get_object(),
                    s.validated_data["status"],
                    request.headers.get("If-Match"),
                )
            ).data
        )


class EnrollmentViewSet(GuardedModelViewSet):
    queryset = EnrollmentSerializer.Meta.model.objects.none()
    serializer_class = EnrollmentSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Enrollment.objects.filter(
            Q(user=self.request.user)
            | Q(classroom__in=classrooms(self.request.user, True))
        ).distinct()

    def perform_create(self, s):
        if not s.validated_data.get("classroom"):
            raise ValidationError({"classroom": "Выберите класс"})
        s.instance = services.enroll(
            self.request.user,
            s.validated_data["course"],
            s.validated_data["user"],
            s.validated_data["classroom"],
        )

    @extend_schema(request=None, responses=EnrollmentSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return Response(
            EnrollmentSerializer(
                services.cancel_enrollment(
                    request.user, self.get_object(), request.headers.get("If-Match")
                )
            ).data
        )


class AssignmentSerializer(RevisionSerializer):
    class Meta:
        model = Assignment
        fields = [
            "id",
            "course",
            "title",
            "instructions",
            "criteria",
            "due_at",
            "position",
            "required",
        ]


class AssignmentViewSet(GuardedModelViewSet):
    queryset = Assignment.objects.none()
    serializer_class = AssignmentSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Assignment.objects.filter(
            course__in=CourseViewSet.get_queryset(self)
        ).order_by("position", "created_at")

    def perform_create(self, s):
        course = s.validated_data["course"]
        require_institution(self.request.user, course.institution)
        if course.status != "draft":
            raise ValidationError("Задания изменяются только в черновике курса")
        s.save()

    def perform_update(self, s):
        course = s.instance.course
        require_institution(self.request.user, course.institution)
        if course.status != "draft" or s.validated_data.get("course", course) != course:
            raise ValidationError("Опубликованное задание и его курс неизменяемы")
        s.save()


class CourseWorkSerializer(RevisionSerializer):
    class Meta:
        model = CourseSubmission
        fields = [
            "id",
            "assignment",
            "enrollment",
            "text",
            "status",
            "previous",
            "submitted_at",
            "reviewer",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["status", "submitted_at", "reviewer", "feedback"]


class CourseReviewInput(serializers.Serializer):
    result = serializers.ChoiceField(choices=["accepted", "revision"])
    feedback = serializers.CharField(allow_blank=True)


class CourseWorkViewSet(GuardedModelViewSet):
    business_update = True
    queryset = CourseSubmission.objects.none()
    serializer_class = CourseWorkSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return (
            CourseSubmission.objects.filter(
                Q(enrollment__user=self.request.user)
                | Q(enrollment__classroom__in=classrooms(self.request.user, True))
            )
            .distinct()
            .order_by("created_at")
        )

    def perform_create(self, s):
        s.instance = services.create_work(self.request.user, s.validated_data)

    def perform_update(self, s):
        if set(s.validated_data) - {"text"}:
            raise ValidationError("Разрешён только текст черновика")
        s.instance = services.edit_work(
            self.request.user,
            s.instance,
            s.validated_data.get("text", s.instance.text),
            self.request.headers.get("If-Match"),
        )

    @extend_schema(request=None, responses=CourseWorkSerializer)
    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        return Response(
            CourseWorkSerializer(
                services.send_work(
                    request.user, self.get_object(), request.headers.get("If-Match")
                )
            ).data
        )

    @extend_schema(request=CourseReviewInput, responses=CourseWorkSerializer)
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        s = CourseReviewInput(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(
            CourseWorkSerializer(
                services.review_work(
                    request.user,
                    self.get_object(),
                    **s.validated_data,
                    expected=request.headers.get("If-Match"),
                )
            ).data
        )
