from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from invitations.services import cipher
from .models import EmailChange


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def deliver_email_change(pk):
    change = EmailChange.objects.get(pk=pk)
    if change.consumed_at or change.expires_at <= timezone.now():
        return
    code = cipher().decrypt(change.encrypted_code.encode()).decode()
    send_mail(
        "Подтверждение новой почты",
        "Код подтверждения: " + code,
        settings.DEFAULT_FROM_EMAIL,
        [change.new_email],
    )
