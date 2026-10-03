import hmac, hashlib, secrets
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from rest_framework.exceptions import ValidationError
from common.services import audit
from invitations.services import cipher
from .models import User, EmailChange


def code_hash(change, code):
    return hmac.new(
        settings.SECRET_KEY.encode(),
        (str(change.pk) + ":" + code).encode(),
        hashlib.sha256,
    ).hexdigest()


@transaction.atomic
def request_email_change(actor, new_email, password):
    actor = User.objects.select_for_update().get(pk=actor.pk)
    if not actor.check_password(password):
        raise ValidationError("Подтвердите текущий пароль")
    new_email = new_email.strip().lower()
    if User.objects.filter(email__iexact=new_email).exists():
        raise ValidationError("Этот email уже используется")
    if EmailChange.objects.filter(
        user=actor, created_at__gt=timezone.now() - timedelta(minutes=1)
    ).exists():
        raise ValidationError("Повторите через минуту")
    EmailChange.objects.filter(user=actor, consumed_at__isnull=True).update(
        consumed_at=timezone.now(), encrypted_code="", code_hash=""
    )
    change = EmailChange(
        user=actor,
        new_email=new_email,
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    code = str(secrets.randbelow(10**6)).zfill(6)
    change.code_hash = code_hash(change, code)
    change.encrypted_code = cipher().encrypt(code.encode()).decode()
    change.save()
    from common.outbox import enqueue

    enqueue("email_change", {"pk": str(change.pk)}, f"email-change:{change.pk}")
    return change


def confirm_email_change(actor, pk, code):
    error = False
    with transaction.atomic():
        actor = User.objects.select_for_update().get(pk=actor.pk)
        change = (
            EmailChange.objects.select_for_update()
            .filter(pk=pk, user=actor, consumed_at__isnull=True)
            .first()
        )
        if not change or change.expires_at <= timezone.now() or change.attempts >= 10:
            raise ValidationError("Запрос недействителен")
        if not hmac.compare_digest(change.code_hash, code_hash(change, code)):
            change.attempts += 1
            change.save()
            error = True
        else:
            if (
                User.objects.filter(email__iexact=change.new_email)
                .exclude(pk=actor.pk)
                .exists()
            ):
                raise ValidationError("Email уже используется")
            old = actor.email
            actor.email = change.new_email
            actor.email_verified_at = timezone.now()
            actor.save(update_fields=["email", "email_verified_at"])
            change.consumed_at = timezone.now()
            change.encrypted_code = ""
            change.code_hash = ""
            change.save()
            audit(
                actor,
                "account.email_changed",
                change,
                details={"old_email": old, "new_email": actor.email},
            )
    if error:
        raise ValidationError("Неверный код подтверждения")
    return actor
