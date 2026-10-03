from common.api import RevisionSerializer, GuardedModelViewSet
from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from common.access import classrooms, require_class, project_access
from common.services import audit
from institutions.models import StudentMembership
from crm.models import LearningActivity
from .models import Project, ProjectMember, Task, Submission, Milestone, ReviewEvent
from . import services


class TransitionSerializer(serializers.Serializer):
    status = serializers.CharField()
    feedback = serializers.CharField(required=False, default="", allow_blank=True)


class ProjectSerializer(RevisionSerializer):
    progress = serializers.SerializerMethodField()
    submitted_tasks = serializers.SerializerMethodField()
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)

    def get_progress(self, obj) -> int:
        total = obj.tasks.count()
        accepted = obj.tasks.filter(submissions__result="accepted").distinct().count()
        return round(accepted * 100 / total) if total else 0

    def get_submitted_tasks(self, obj) -> int:
        return (
            obj.tasks.filter(
                submissions__result__in=["submitted", "accepted", "revision"]
            )
            .distinct()
            .count()
        )

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "description",
            "classroom",
            "classroom_name",
            "members",
            "progress",
            "submitted_tasks",
            "updated_at",
            "status",
            "due_at",
        ]
        read_only_fields = ["members", "status"]


class MemberSerializer(RevisionSerializer):
    name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = ProjectMember
        fields = ["id", "project", "user", "role", "name"]


class TaskSerializer(RevisionSerializer):
    def validate(self, data):
        project = data.get("project", self.instance.project if self.instance else None)
        milestone = data.get(
            "milestone", self.instance.milestone if self.instance else None
        )
        if milestone and milestone.project_id != project.pk:
            raise serializers.ValidationError({"milestone": "Этап другого проекта"})
        return data

    class Meta:
        model = Task
        fields = ["id", "project", "title", "stage", "due_at", "criteria", "milestone"]


class SubmissionSerializer(RevisionSerializer):
    draft = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Submission
        fields = [
            "id",
            "task",
            "author",
            "text",
            "result",
            "reviewer",
            "feedback",
            "created_at",
            "previous",
            "document_version",
            "draft",
            "submitted_at",
        ]
        read_only_fields = ["author", "result", "reviewer", "feedback", "submitted_at"]


class ReviewSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=["accepted", "revision"])
    feedback = serializers.CharField(allow_blank=True)


def projects_for(u):
    if not u.is_authenticated or not u.is_active:
        return Project.objects.none()
    return Project.objects.filter(
        Q(classroom__in=classrooms(u, True)) | Q(members=u)
    ).distinct()


class ProjectViewSet(GuardedModelViewSet):
    queryset = ProjectSerializer.Meta.model.objects.none()
    serializer_class = ProjectSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return projects_for(self.request.user).prefetch_related("tasks__submissions")

    def perform_create(self, s):
        cl = s.validated_data["classroom"]
        require_class(self.request.user, cl, True)
        obj = s.save()
        audit(self.request.user, "project.created", obj, cl.institution)

    def perform_update(self, s):
        project_access(self.request.user, s.instance)
        if s.instance.status in ("accepted", "archived"):
            raise ValidationError("Закрытый проект неизменяем")
        if "due_at" in s.validated_data:
            project_access(self.request.user, s.instance, True)
        if (
            s.validated_data.get("classroom", s.instance.classroom)
            != s.instance.classroom
        ):
            raise ValidationError("Класс проекта неизменяем")
        obj = s.save()
        LearningActivity.objects.create(
            actor=self.request.user,
            classroom=obj.classroom,
            kind="project.updated",
            target=str(obj.pk),
        )

    @extend_schema(request=TransitionSerializer, responses=ProjectSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        data = TransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(
            ProjectSerializer(
                services.transition_project(
                    request.user,
                    self.get_object(),
                    **data.validated_data,
                    expected=request.headers.get("If-Match"),
                )
            ).data
        )


class MemberViewSet(GuardedModelViewSet):
    queryset = MemberSerializer.Meta.model.objects.none()
    serializer_class = MemberSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return ProjectMember.objects.filter(project__in=projects_for(self.request.user))

    def perform_create(self, s):
        p = s.validated_data["project"]
        u = s.validated_data["user"]
        project_access(self.request.user, p, True)
        if not StudentMembership.objects.filter(
            user=u, classroom=p.classroom, ended_at__isnull=True
        ).exists():
            raise ValidationError("Участник другого класса")
        obj = s.save()
        audit(
            self.request.user,
            "project.member_added",
            obj,
            p.classroom.institution,
            {"user": str(u.pk), "role": obj.role},
        )

    def perform_update(self, s):
        project_access(self.request.user, s.instance.project, True)
        if set(s.validated_data) - {"role"}:
            raise ValidationError("Разрешено менять только роль в команде")
        obj = s.save()
        audit(
            self.request.user,
            "project.member_role_changed",
            obj,
            obj.project.classroom.institution,
            {"role": obj.role},
        )


class TaskViewSet(GuardedModelViewSet):
    queryset = TaskSerializer.Meta.model.objects.none()
    serializer_class = TaskSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Task.objects.filter(project__in=projects_for(self.request.user))

    def perform_create(self, s):
        project_access(self.request.user, s.validated_data["project"], True)
        s.save()

    def perform_update(self, s):
        project_access(self.request.user, s.instance.project, True)
        if s.instance.submissions.exists():
            raise ValidationError("Задание с историей отправок неизменяемо")
        if s.validated_data.get("project", s.instance.project) != s.instance.project:
            raise ValidationError("Проект задания неизменяем")
        s.save()


class SubmissionViewSet(GuardedModelViewSet):
    business_update = True
    queryset = SubmissionSerializer.Meta.model.objects.none()
    serializer_class = SubmissionSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Submission.objects.filter(
            task__project__in=projects_for(self.request.user)
        )

    def perform_create(self, s):
        task = s.validated_data["task"]
        project_access(self.request.user, task.project)
        values = dict(s.validated_data)
        draft = values.pop("draft", False)
        s.instance = services.create_submission(self.request.user, values, draft)

    @extend_schema(request=ReviewSerializer, responses=SubmissionSerializer)
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        obj = self.get_object()
        project_access(request.user, obj.task.project, True)
        s = ReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        obj = services.review_submission(
            request.user,
            obj,
            **s.validated_data,
            expected=request.headers.get("If-Match"),
        )
        return Response(SubmissionSerializer(obj).data)

    def perform_update(self, s):
        if set(s.validated_data) - {"text"}:
            raise ValidationError("Разрешено редактировать только текст черновика")
        s.instance = services.edit_draft(
            self.request.user,
            s.instance,
            s.validated_data.get("text", s.instance.text),
            self.request.headers.get("If-Match"),
        )

    @extend_schema(request=None, responses=SubmissionSerializer)
    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        return Response(
            SubmissionSerializer(
                services.send_draft(
                    request.user, self.get_object(), request.headers.get("If-Match")
                )
            ).data
        )


class MilestoneSerializer(RevisionSerializer):
    class Meta:
        model = Milestone
        fields = ["id", "project", "title", "criteria", "due_at", "position", "status"]
        read_only_fields = ["status"]


class MilestoneViewSet(GuardedModelViewSet):
    queryset = Milestone.objects.none()
    serializer_class = MilestoneSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Milestone.objects.filter(
            project__in=projects_for(self.request.user)
        ).order_by("position")

    def perform_create(self, s):
        project_access(self.request.user, s.validated_data["project"], True)
        s.save()

    def perform_update(self, s):
        project_access(self.request.user, s.instance.project, True)
        if s.validated_data.get("project", s.instance.project) != s.instance.project:
            raise ValidationError("Проект этапа неизменяем")
        s.save()

    @extend_schema(request=TransitionSerializer, responses=MilestoneSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        data = TransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(
            MilestoneSerializer(
                services.transition_milestone(
                    request.user,
                    self.get_object(),
                    data.validated_data["status"],
                    request.headers.get("If-Match"),
                )
            ).data
        )


class ReviewEventSerializer(RevisionSerializer):
    class Meta:
        model = ReviewEvent
        fields = ["id", "submission", "reviewer", "result", "feedback", "created_at"]
        read_only_fields = fields


class ReviewHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReviewEvent.objects.none()
    serializer_class = ReviewEventSerializer

    def get_queryset(self):
        return ReviewEvent.objects.filter(
            submission__task__project__in=projects_for(self.request.user)
        ).order_by("created_at")
