from common.api import RevisionSerializer, GuardedModelViewSet
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.db.models import Q
from django.db import transaction
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
        require_institution(
            self.request.user,
            s.validated_data["institution"],
            roles=("admin", "curator", "teacher"),
        )
        s.save()

    def perform_update(self, s):
        require_institution(
            self.request.user,
            s.instance.institution,
            roles=("admin", "curator", "teacher"),
        )
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

    @transaction.atomic
    def perform_create(self, s):
        course = Course.objects.select_for_update().get(
            pk=s.validated_data["course"].pk
        )
        require_institution(
            self.request.user, course.institution, roles=("admin", "curator", "teacher")
        )
        if course.status != "draft":
            raise ValidationError("Задания изменяются только в черновике курса")
        s.save()

    @transaction.atomic
    def perform_update(self, s):
        course = Course.objects.select_for_update().get(pk=s.instance.course_id)
        require_institution(
            self.request.user, course.institution, roles=("admin", "curator", "teacher")
        )
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


class CourseMaterialSerializer(RevisionSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)

    class Meta:
        from .models import CourseMaterial

        model = CourseMaterial
        fields = [
            "id",
            "course",
            "title",
            "author",
            "author_name",
            "filename",
            "size",
            "teaching_resource",
            "created_at",
        ]
        read_only_fields = fields


class CourseMaterialUploadSerializer(serializers.Serializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    title = serializers.CharField(max_length=200)
    file = serializers.FileField()


class CourseMaterialViewSet(GuardedModelViewSet):
    from .models import CourseMaterial

    queryset = CourseMaterial.objects.none()
    serializer_class = CourseMaterialSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        from .models import CourseMaterial
        from common.access import institution_ids

        qs = CourseMaterial.objects.filter(course__in=CourseViewSet.get_queryset(self))
        qs = qs.filter(
            Q(teaching_resource=True)
            | Q(author=self.request.user)
            | Q(
                course__institution_id__in=institution_ids(
                    self.request.user, ["admin", "curator", "teacher"]
                )
            )
        )
        course = self.request.query_params.get("course")
        return (qs.filter(course_id=course) if course else qs).order_by("created_at")

    @extend_schema(
        request=CourseMaterialUploadSerializer, responses=CourseMaterialSerializer
    )
    def create(self, request, *args, **kwargs):
        from pathlib import Path
        import uuid
        from django.core.files.base import ContentFile
        from django.db import transaction
        from common.access import institution_ids, require_class
        from .models import CourseMaterial

        s = CourseMaterialUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        values = s.validated_data
        with transaction.atomic():
            course = Course.objects.select_for_update().get(pk=values["course"].pk)
            staff = course.institution_id in institution_ids(
                request.user, ["admin", "curator", "teacher"]
            )
            if not staff:
                enrollment = Enrollment.objects.filter(
                    course=course, user=request.user, status="active"
                ).first()
                if not enrollment:
                    from rest_framework.exceptions import PermissionDenied

                    raise PermissionDenied("Нужна активная запись на курс")
                require_class(request.user, enrollment.classroom)
            if course.status == "archived" or (
                not staff and course.status != "published"
            ):
                raise ValidationError("Загрузка в этот курс закрыта")
            upload = values["file"]
            from common.uploads import validate_attachment

            content, ext, _ = validate_attachment(upload)
            obj = CourseMaterial(
                course=course,
                author=request.user,
                title=values["title"],
                filename=Path(upload.name).name[:200],
                size=len(content),
                teaching_resource=staff,
            )
            obj.file.save(str(uuid.uuid4()) + ext, ContentFile(content), save=False)
            obj.save()
        return Response(CourseMaterialSerializer(obj).data, status=201)

    @extend_schema(responses={(200, "application/octet-stream"): bytes})
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        from django.http import FileResponse

        obj = self.get_object()
        response = FileResponse(
            obj.file.open("rb"), as_attachment=True, filename=obj.filename
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class CourseLessonSerializer(RevisionSerializer):
    completed = serializers.SerializerMethodField()

    def get_completed(self, obj) -> bool:
        from .models import LessonCompletion

        return LessonCompletion.objects.filter(
            lesson=obj, enrollment__user=self.context["request"].user
        ).exists()

    class Meta:
        from .models import CourseLesson

        model = CourseLesson
        fields = ["id", "course", "title", "body", "position", "completed"]


class CourseLessonViewSet(GuardedModelViewSet):
    from .models import CourseLesson

    queryset = CourseLesson.objects.none()
    serializer_class = CourseLessonSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        from .models import CourseLesson

        return CourseLesson.objects.filter(
            course__in=CourseViewSet.get_queryset(self)
        ).order_by("position", "created_at")

    @transaction.atomic
    def perform_create(self, s):
        course = Course.objects.select_for_update().get(
            pk=s.validated_data["course"].pk
        )
        require_institution(
            self.request.user, course.institution, roles=("admin", "curator", "teacher")
        )
        if course.status != "draft":
            raise ValidationError("Уроки изменяются только в черновике")
        s.save()

    @transaction.atomic
    def perform_update(self, s):
        course = Course.objects.select_for_update().get(pk=s.instance.course_id)
        require_institution(
            self.request.user, course.institution, roles=("admin", "curator", "teacher")
        )
        if course.status != "draft" or s.validated_data.get("course", course) != course:
            raise ValidationError("Опубликованный урок и его курс неизменяемы")
        s.save()

    @extend_schema(request=None, responses=EnrollmentSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return Response(
            EnrollmentSerializer(
                services.complete_lesson(request.user, self.get_object())
            ).data
        )
