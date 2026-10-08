from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from accounts.views import (
    ProfileView,
    RegistrationRequestView,
    RegistrationConfirmView,
    SessionView,
    LoginView,
    LogoutView,
    EmailChangeRequestView,
    EmailChangeConfirmView,
)
from institutions.views import (
    InstitutionViewSet,
    ClassroomViewSet,
    StaffViewSet,
    TeachingViewSet,
    MembershipViewSet,
)
from courses.views import (
    CourseViewSet,
    EnrollmentViewSet,
    AssignmentViewSet,
    CourseWorkViewSet,
    CourseMaterialViewSet,
    CourseLessonViewSet,
)
from projects.views import (
    ProjectViewSet,
    MemberViewSet,
    TaskViewSet,
    SubmissionViewSet,
    MilestoneViewSet,
    ReviewHistoryViewSet,
)
from documents.views import DocumentViewSet, VersionViewSet, ComparisonViewSet
from invitations.views import (
    InvitationViewSet,
    ProspectViewSet,
    ImportViewSet,
    RequestCodeView,
    AcceptView,
    ExportView,
    TemplateView,
)
from scheduling.views import LessonViewSet, AttendanceViewSet
from publications.views import (
    PublicationViewSet,
    CompetitionViewSet,
    TopicViewSet,
    ApplicationViewSet,
)
from workshops.views import (
    WorkshopViewSet,
    GroupViewSet,
    RegistrationViewSet,
    PartnershipViewSet,
    SubscriptionViewSet,
)
from crm.views import MetricsView
from common.views import live, ready, NotificationViewSet

from integrations.views import (
    RepositoryViewSet,
    PullViewSet,
    ReviewViewSet,
    SyncViewSet,
    WebhookView,
)

from accounts.management_views import ManagedUserViewSet

router = DefaultRouter()
for prefix, view in [
    ("institutions", InstitutionViewSet),
    ("users", ManagedUserViewSet),
    ("repositories", RepositoryViewSet),
    ("pull-requests", PullViewSet),
    ("git-reviews", ReviewViewSet),
    ("git-sync", SyncViewSet),
    ("classrooms", ClassroomViewSet),
    ("staff", StaffViewSet),
    ("teaching-assignments", TeachingViewSet),
    ("memberships", MembershipViewSet),
    ("courses", CourseViewSet),
    ("course-materials", CourseMaterialViewSet),
    ("course-lessons", CourseLessonViewSet),
    ("assignments", AssignmentViewSet),
    ("course-submissions", CourseWorkViewSet),
    ("milestones", MilestoneViewSet),
    ("review-history", ReviewHistoryViewSet),
    ("comparisons", ComparisonViewSet),
    ("enrollments", EnrollmentViewSet),
    ("projects", ProjectViewSet),
    ("project-members", MemberViewSet),
    ("tasks", TaskViewSet),
    ("submissions", SubmissionViewSet),
    ("documents", DocumentViewSet),
    ("document-versions", VersionViewSet),
    ("invitations", InvitationViewSet),
    ("prospects", ProspectViewSet),
    ("imports", ImportViewSet),
    ("lessons", LessonViewSet),
    ("attendance", AttendanceViewSet),
    ("publications", PublicationViewSet),
    ("competitions", CompetitionViewSet),
    ("competition-applications", ApplicationViewSet),
    ("topics", TopicViewSet),
    ("workshops", WorkshopViewSet),
    ("workshop-groups", GroupViewSet),
    ("registrations", RegistrationViewSet),
    ("partnerships", PartnershipViewSet),
    ("subscriptions", SubscriptionViewSet),
    ("notifications", NotificationViewSet),
]:
    router.register(prefix, view, basename=prefix)
urlpatterns = [
    path("api/profile/", ProfileView.as_view()),
    path("api/registration/request/", RegistrationRequestView.as_view()),
    path("api/registration/confirm/", RegistrationConfirmView.as_view()),
    path("api/webhooks/<uuid:pk>/", WebhookView.as_view()),
    path("api/email-change/request/", EmailChangeRequestView.as_view()),
    path("api/email-change/confirm/", EmailChangeConfirmView.as_view()),
    path("admin/", admin.site.urls),
    path("health/live/", live),
    path("health/ready/", ready),
    path("api/session/", SessionView.as_view()),
    path("api/login/", LoginView.as_view()),
    path("api/logout/", LogoutView.as_view()),
    path("api/invitation-code/", RequestCodeView.as_view()),
    path("api/invitation-accept/", AcceptView.as_view()),
    path("api/classrooms/<uuid:pk>/export/", ExportView.as_view()),
    path("api/import-template/", TemplateView.as_view()),
    path("api/crm/", MetricsView.as_view()),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/", include(router.urls)),
]

# Preserve existing routes while making v1 the canonical generated contract.
from django.urls.resolvers import URLPattern

api_patterns = [
    path(entry.pattern._route.removeprefix("api/"), entry.callback, name=entry.name)
    for entry in urlpatterns
    if isinstance(entry, URLPattern) and str(entry.pattern).startswith("api/")
]
api_patterns.append(path("", include(router.urls)))
urlpatterns.insert(0, path("api/v1/", include(api_patterns)))
