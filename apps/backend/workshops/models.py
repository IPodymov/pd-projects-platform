from django.db import models
from common.models import Entity


class Partnership(Entity):
    university = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="university_partnerships",
    )
    school = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.PROTECT,
        related_name="school_partnerships",
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Действует"),
            ("pending", "Ожидает"),
            ("ended", "Завершено"),
        ],
    )
    starts_on = models.DateField()
    ends_on = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["university", "school"], name="unique_partnership"
            )
        ]


class Workshop(Entity):
    university = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT)
    organizer = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    description = models.TextField()
    topic = models.CharField(max_length=100)
    min_age = models.PositiveSmallIntegerField(default=0)
    max_age = models.PositiveSmallIntegerField(default=99)
    requirements = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    format = models.CharField(
        max_length=20, choices=[("online", "Онлайн"), ("onsite", "Очно")]
    )
    location = models.CharField(max_length=200)
    capacity = models.PositiveIntegerField()
    registration_opens_at = models.DateTimeField()
    registration_closes_at = models.DateTimeField()
    audience = models.CharField(
        max_length=20,
        choices=[
            ("all", "Все"),
            ("partners", "Партнёры"),
            ("selected", "Выбранные школы"),
        ],
    )
    schools = models.ManyToManyField(
        "institutions.Institution", related_name="targeted_workshops", blank=True
    )
    published = models.BooleanField(default=False)
    cancelled = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    online_url = models.URLField(blank=True)
    leader = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        related_name="led_workshops",
        on_delete=models.PROTECT,
    )

    @property
    def status(self):
        return (
            "cancelled"
            if self.cancelled
            else "completed"
            if self.completed
            else "published"
            if self.published
            else "draft"
        )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(starts_at__lt=models.F("ends_at")),
                name="workshop_time_order",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    registration_opens_at__lt=models.F("registration_closes_at")
                ),
                name="workshop_registration_order",
            ),
            models.CheckConstraint(
                condition=models.Q(capacity__gt=0), name="workshop_positive_capacity"
            ),
            models.CheckConstraint(
                condition=models.Q(min_age__lte=models.F("max_age")),
                name="workshop_age_order",
            ),
        ]


class GroupApplication(Entity):
    workshop = models.ForeignKey(Workshop, on_delete=models.PROTECT)
    school = models.ForeignKey("institutions.Institution", on_delete=models.PROTECT)
    responsible = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20,
        choices=[
            ("confirmed", "Подтверждена"),
            ("waiting", "Ожидает"),
            ("cancelled", "Отменена"),
        ],
        default="waiting",
    )


class Registration(Entity):
    workshop = models.ForeignKey(
        Workshop, related_name="registrations", on_delete=models.PROTECT
    )
    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    group = models.ForeignKey(
        GroupApplication, null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("confirmed", "Подтверждено"),
            ("waiting", "Лист ожидания"),
            ("cancelled", "Отменено"),
        ],
    )
    attended = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workshop", "user"], name="unique_workshop_person"
            )
        ]


class Subscription(Entity):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    school = models.ForeignKey("institutions.Institution", on_delete=models.CASCADE)
    email_enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "school"], name="unique_workshop_subscription"
            )
        ]
