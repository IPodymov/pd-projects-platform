from celery import shared_task
from django.utils import timezone
from common.access import institution_ids
from common.services import notify
from django.db import transaction
from .models import Workshop, Subscription


@shared_task
def announce_registration_openings():
    now = timezone.now()
    for workshop in Workshop.objects.filter(
        published=True,
        cancelled=False,
        completed=False,
        registration_opens_at__lte=now,
        registration_closes_at__gt=now,
    ):
        partners = workshop.university.university_partnerships.filter(
            status="active", starts_on__lte=now.date(), ends_on__gte=now.date()
        )
        subscriptions = Subscription.objects.filter(
            school_id__in=partners.values("school_id")
        ).select_related("user")
        if workshop.audience == "selected":
            subscriptions = subscriptions.filter(school__in=workshop.schools.all())
        with transaction.atomic():
            for sub in subscriptions:
                if sub.school_id in institution_ids(sub.user):
                    notify(
                        [sub.user],
                        "Открыта регистрация: " + workshop.title,
                        email=sub.email_enabled,
                        kind="workshop.opened",
                        target=workshop.pk,
                        event_key=f"workshop-opened:{workshop.pk}",
                    )
