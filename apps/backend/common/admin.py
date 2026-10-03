from django.contrib import admin
from django.apps import apps
from django.contrib.auth.admin import UserAdmin
from accounts.models import User


class PlatformAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


class ImmutableAdmin(PlatformAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class InvitationAdmin(ImmutableAdmin):
    exclude = ["token_hash", "encrypted_token", "code_hash"]


class PlatformUserAdmin(UserAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(User, PlatformUserAdmin)
for label in [
    "institutions",
    "courses",
    "projects",
    "documents",
    "integrations",
    "publications",
    "invitations",
    "scheduling",
    "crm",
    "workshops",
    "common",
]:
    for model in apps.get_app_config(label).get_models():
        cls = (
            InvitationAdmin
            if model.__name__ == "Invitation"
            else ImmutableAdmin
            if model.__name__
            in [
                "EmailChange",
                "DocumentVersion",
                "AuditEvent",
                "LearningActivity",
                "SeedReceipt",
                "ImportBatch",
                "Outbox",
                "Notification",
                "Comparison",
                "CourseReview",
                "ReviewEvent",
                "ProjectTransition",
                "ApplicationTransition",
                "LearningReview",
                "WebhookEvent",
                "SyncJob",
                "CourseSubmission",
                "Submission",
                "Enrollment",
                "CompetitionApplication",
                "Registration",
                "GroupApplication",
                "Lesson",
                "Series",
                "Attendance",
            ]
            else PlatformAdmin
        )
        admin.site.register(model, cls)
admin.site.site_header = "Инженеры будущего — управление"

from accounts.models import EmailChange

admin.site.register(EmailChange, ImmutableAdmin)
