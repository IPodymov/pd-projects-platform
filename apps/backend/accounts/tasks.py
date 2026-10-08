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


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def deliver_registration(pk):
    from .models import RegistrationRequest

    pending = RegistrationRequest.objects.get(pk=pk)
    if pending.consumed_at or pending.expires_at <= timezone.now():
        return
    code = cipher().decrypt(pending.encrypted_code.encode()).decode()
    send_mail(
        "Подтверждение регистрации — Инженеры будущего",
        "Код подтверждения: " + code + "\nКод действует 15 минут.",
        settings.DEFAULT_FROM_EMAIL,
        [pending.email],
    )


@shared_task
def expire_registrations():
    from .models import RegistrationRequest

    RegistrationRequest.objects.filter(expires_at__lte=timezone.now()).update(
        password_hash="",
        code_hash="",
        encrypted_code="",
    )
