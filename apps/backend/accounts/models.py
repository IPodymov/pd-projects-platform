from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    display_name = models.CharField(max_length=200, blank=True)

    def get_full_name(self):
        return self.display_name or super().get_full_name()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("email"), name="unique_email_case_insensitive"
            )
        ]


from common.models import Entity


class EmailChange(Entity):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    new_email = models.EmailField()
    code_hash = models.CharField(max_length=64)
    encrypted_code = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)


class LoginEvent(Entity):
    user = models.ForeignKey(
        User, related_name="login_events", on_delete=models.PROTECT
    )
