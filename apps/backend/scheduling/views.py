from common.api import RevisionSerializer, GuardedModelViewSet
from django.db.models import Q
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from common.access import classrooms
from .models import Lesson, Attendance
from .services import create_lesson, change_lesson


class LessonSerializer(RevisionSerializer):
    repeat_weeks = serializers.IntegerField(
        min_value=1, max_value=52, default=1, write_only=True
    )

    class Meta:
        model = Lesson
        fields = [
            "id",
            "title",
            "description",
            "classroom",
            "course",
            "teacher",
            "curator",
            "starts_at",
            "ends_at",
            "timezone",
            "format",
            "status",
            "online_url",
            "location",
            "room",
            "series",
            "occurrence",
            "is_exception",
            "repeat_weeks",
        ]
        read_only_fields = ["series", "occurrence", "is_exception"]


class LessonChangeSerializer(RevisionSerializer):
    class Meta:
        model = Lesson
        fields = [
            "title",
            "description",
            "starts_at",
            "ends_at",
            "timezone",
            "format",
            "status",
            "online_url",
            "location",
            "room",
        ]
        extra_kwargs = {f: {"required": False} for f in fields}


class AttendanceSerializer(RevisionSerializer):
    class Meta:
        model = Attendance
        fields = ["id", "lesson", "user", "present"]
        validators = []


class LessonViewSet(GuardedModelViewSet):
    business_update = True
    queryset = LessonSerializer.Meta.model.objects.none()
    serializer_class = LessonSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        q = (
            Lesson.objects.filter(classroom__in=classrooms(self.request.user))
            .filter(
                Q(course__isnull=True)
                | Q(classroom__in=classrooms(self.request.user, True))
                | Q(
                    course__enrollment__user=self.request.user,
                    course__enrollment__status__in=["active", "completed"],
                )
            )
            .distinct()
            .order_by("starts_at")
        )
        for param, lookup in [("from", "starts_at__gte"), ("to", "starts_at__lt")]:
            if self.request.query_params.get(param):
                from django.utils.dateparse import parse_datetime

                try:
                    v = parse_datetime(self.request.query_params[param])
                except ValueError:
                    v = None
                if not v or not v.tzinfo:
                    raise ValidationError("Укажите ISO datetime с часовым поясом")
                q = q.filter(**{lookup: v})
        return q

    def perform_create(self, s):
        d = dict(s.validated_data)
        weeks = d.pop("repeat_weeks", 1)
        s.instance = create_lesson(self.request.user, d, weeks)[0]

    def perform_update(self, s):
        d = dict(s.validated_data)
        d.pop("repeat_weeks", None)
        if (
            self.request.path.startswith("/api/v1/")
            and d.get("status", s.instance.status) != s.instance.status
        ):
            raise ValidationError(
                {"status": "Используйте действие change для перехода статуса"}
            )
        s.instance = change_lesson(
            self.request.user,
            s.instance,
            d,
            expected=self.request.headers.get("If-Match"),
        )

    @extend_schema(request=LessonChangeSerializer, responses=LessonSerializer)
    @action(detail=True, methods=["post"])
    def change_series(self, request, pk=None):
        s = LessonChangeSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        return Response(
            LessonSerializer(
                change_lesson(
                    request.user,
                    self.get_object(),
                    s.validated_data,
                    True,
                    request.headers.get("If-Match"),
                )
            ).data
        )

    @extend_schema(request=LessonChangeSerializer, responses=LessonSerializer)
    @action(detail=True, methods=["post"])
    def change(self, request, pk=None):
        s = LessonChangeSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        return Response(
            LessonSerializer(
                change_lesson(
                    request.user,
                    self.get_object(),
                    s.validated_data,
                    expected=request.headers.get("If-Match"),
                )
            ).data
        )


class AttendanceViewSet(GuardedModelViewSet):
    queryset = AttendanceSerializer.Meta.model.objects.none()
    serializer_class = AttendanceSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Attendance.objects.filter(
            lesson__classroom__in=classrooms(self.request.user, True)
        )

    business_update = True

    def perform_create(self, s):
        from .services import record_class_attendance

        s.instance = record_class_attendance(
            self.request.user,
            s.validated_data["lesson"],
            s.validated_data["user"],
            s.validated_data.get("present", False),
        )

    def perform_update(self, s):
        from .services import record_class_attendance

        if set(s.validated_data) - {"present"}:
            raise ValidationError("Разрешено менять только присутствие")
        s.instance = record_class_attendance(
            self.request.user,
            s.instance.lesson,
            s.instance.user,
            s.validated_data.get("present", s.instance.present),
            s.instance,
            self.request.headers.get("If-Match"),
        )
