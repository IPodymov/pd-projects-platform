from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter
from common.access import classrooms
from institutions.models import TeachingAssignment
from accounts.models import User, LoginEvent
from invitations.models import Prospect, Invitation
from projects.models import Project, Task
from courses.models import Enrollment, Assignment, CourseSubmission
from scheduling.models import Attendance
from workshops.models import Registration
from .models import LearningActivity


class MetricsSerializer(serializers.Serializer):
    updated_at = serializers.DateTimeField()
    period = serializers.DictField()
    learning = serializers.DictField()
    workshops = serializers.DictField()
    classrooms = serializers.ListField(child=serializers.DictField())
    participants = serializers.ListField(child=serializers.DictField())


class MetricsView(APIView):
    @extend_schema(
        responses=MetricsSerializer,
        parameters=[
            OpenApiParameter(k, str)
            for k in ["institution", "classroom", "teacher", "course", "from", "to"]
        ],
    )
    def get(self, request):
        now = timezone.now()
        start = now - timedelta(days=30)
        end = now
        for key in ["from", "to"]:
            if request.query_params.get(key):
                try:
                    dt = parse_datetime(request.query_params[key])
                except ValueError:
                    dt = None
                if not dt or not dt.tzinfo:
                    raise ValidationError("Период: ISO datetime с часовым поясом")
                if key == "from":
                    start = dt
                else:
                    end = dt
        if start >= end or end - start > timedelta(days=366):
            raise ValidationError("Период должен быть от 1 секунды до 366 дней")
        cls = classrooms(request.user, True)
        for key, field in [("institution", "institution_id"), ("classroom", "pk")]:
            if request.query_params.get(key):
                cls = cls.filter(**{field: request.query_params[key]})
        if request.query_params.get("teacher"):
            cls = cls.filter(
                id__in=TeachingAssignment.objects.filter(
                    staff__user_id=request.query_params["teacher"],
                    staff__active=True,
                    active=True,
                ).values("classroom_id")
            )
        users = User.objects.filter(studentmembership__classroom__in=cls).distinct()
        if request.query_params.get("course"):
            enrollments = Enrollment.objects.filter(
                course_id=request.query_params["course"], classroom__in=cls
            )
            cls = cls.filter(pk__in=enrollments.values("classroom_id"))
            users = users.filter(pk__in=enrollments.values("user_id"))
        activities = LearningActivity.objects.filter(
            classroom__in=cls,
            actor__in=users,
            created_at__gte=start,
            created_at__lt=end,
        )
        projects = Project.objects.filter(classroom__in=cls)
        tasks = Task.objects.filter(project__in=projects)
        accepted = tasks.filter(submissions__result="accepted").distinct()
        registrations = Registration.objects.filter(user__in=users)
        course_enrollments = Enrollment.objects.filter(
            classroom__in=cls, user__in=users
        )
        if request.query_params.get("course"):
            course_enrollments = course_enrollments.filter(
                course_id=request.query_params["course"]
            )
        course_works = CourseSubmission.objects.filter(
            enrollment__in=course_enrollments
        )
        course_tasks = Assignment.objects.filter(
            course_id__in=course_enrollments.values("course_id")
        )
        accepted_works = course_works.filter(status="accepted")
        overdue_course = 0
        for enrollment in course_enrollments.filter(status="active"):
            overdue_course += (
                enrollment.course.assignments.filter(required=True, due_at__lt=now)
                .exclude(
                    pk__in=accepted_works.filter(enrollment=enrollment).values(
                        "assignment_id"
                    )
                )
                .count()
            )
        # Main education and workshops intentionally have separate counters.
        return Response(
            {
                "updated_at": now,
                "period": {"from": start, "to": end},
                "learning": {
                    "registered": users.count(),
                    "email_verified": users.filter(
                        email_verified_at__isnull=False
                    ).count(),
                    "logged_in_during_period": users.filter(
                        login_events__created_at__gte=start,
                        login_events__created_at__lt=end,
                    )
                    .distinct()
                    .count(),
                    "login_events": LoginEvent.objects.filter(
                        user__in=users, created_at__gte=start, created_at__lt=end
                    ).count(),
                    "educationally_active": activities.values("actor")
                    .distinct()
                    .count(),
                    "learning_actions": activities.count(),
                    "invited_unregistered": Prospect.objects.filter(
                        classroom__in=cls, user__isnull=True
                    ).count(),
                    "pending_invitations": Invitation.objects.filter(
                        classroom__in=cls, status="pending", expires_at__gt=now
                    ).count(),
                    "enrollments": Enrollment.objects.filter(
                        classroom__in=cls, user__in=users
                    ).count(),
                    "attendance_present": Attendance.objects.filter(
                        lesson__classroom__in=cls,
                        user__in=users,
                        present=True,
                        lesson__starts_at__gte=start,
                        lesson__starts_at__lt=end,
                    ).count(),
                    "course_submitted_works": course_works.exclude(
                        status="draft"
                    ).count(),
                    "course_accepted_works": accepted_works.count(),
                    "course_completed_enrollments": course_enrollments.filter(
                        status="completed"
                    ).count(),
                    "course_overdue_assignments": overdue_course,
                    "course_assignments": course_tasks.count(),
                    "projects": projects.count(),
                    "tasks": tasks.count(),
                    "accepted_tasks": accepted.count(),
                    "submitted_tasks": tasks.filter(
                        submissions__result__in=["submitted", "accepted", "revision"]
                    )
                    .distinct()
                    .count(),
                    "overdue_tasks": tasks.filter(due_at__lt=now)
                    .exclude(pk__in=accepted.values("pk"))
                    .count(),
                    "projects_requiring_attention": projects.filter(
                        tasks__in=tasks.filter(due_at__lt=now).exclude(
                            pk__in=accepted.values("pk")
                        )
                    )
                    .distinct()
                    .count(),
                    "progress_percent": round(accepted.count() * 100 / tasks.count())
                    if tasks.exists()
                    else 0,
                },
                "workshops": {
                    "confirmed": registrations.filter(status="confirmed").count(),
                    "waiting": registrations.filter(status="waiting").count(),
                    "attended": registrations.filter(attended=True).count(),
                },
                "participants": list(
                    users.order_by("pk").values(
                        "id",
                        "display_name",
                        "first_name",
                        "last_name",
                        "email",
                        "email_verified_at",
                    )[:500]
                ),
                "classrooms": list(
                    cls.values("id", "name", "academic_year", "institution_id")
                ),
            }
        )
