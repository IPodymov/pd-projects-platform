"""Public email-confirmed signup, independent of institution invitations."""

import hmac
import secrets
import uuid
from datetime import timedelta
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from common.services import audit
from common.outbox import enqueue
from invitations.services import cipher
from .models import User, RegistrationRequest
from .services import code_hash


@transaction.atomic
def request_registration(values):
    email = values["email"].strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError(
            {"email": "Этот email уже зарегистрирован. Войдите в аккаунт."}
        )
    prospective = User(email=email, display_name=values["display_name"])
    validate_password(values["password"], prospective)
    now = timezone.now()
    # The normalized email uniqueness also serializes concurrent first requests.
    pending, created = RegistrationRequest.objects.select_for_update().get_or_create(
        email=email,
        defaults={"display_name": "", "expires_at": now},
    )
    if not created and pending.updated_at > now - timedelta(minutes=1):
        raise ValidationError("Повторная отправка доступна через минуту")
    pending.display_name = values["display_name"]
    pending.date_of_birth = values.get("date_of_birth")
    pending.password_hash = make_password(values["password"])
    pending.expires_at = now + timedelta(minutes=15)
    pending.attempts = 0
    pending.consumed_at = None
    code = str(secrets.randbelow(10**6)).zfill(6)
    pending.code_hash = code_hash(pending, code)
    pending.encrypted_code = cipher().encrypt(code.encode()).decode()
    pending.save()
    enqueue(
        "registration",
        {"pk": str(pending.pk)},
        f"registration:{pending.pk}:{pending.updated_at.isoformat()}",
    )
    return pending


def confirm_registration(pk, code):
    wrong_code = False
    with transaction.atomic():
        pending = (
            RegistrationRequest.objects.select_for_update()
            .filter(pk=pk, consumed_at__isnull=True)
            .first()
        )
        if not pending or pending.expires_at <= timezone.now() or pending.attempts >= 5:
            raise ValidationError(
                "Запрос истёк или недействителен. Запросите новый код."
            )
        if not hmac.compare_digest(pending.code_hash, code_hash(pending, code)):
            pending.attempts += 1
            # Attempts must survive the error response without resetting resend cooldown.
            pending.save(update_fields=["attempts"])
            wrong_code = True
        else:
            if User.objects.filter(email__iexact=pending.email).exists():
                raise ValidationError(
                    {"email": "Этот email уже зарегистрирован. Войдите в аккаунт."}
                )
            user = User.objects.create(
                username=str(uuid.uuid4()),
                email=pending.email,
                display_name=pending.display_name,
                date_of_birth=pending.date_of_birth,
                password=pending.password_hash,
                email_verified_at=timezone.now(),
            )
            pending.consumed_at = timezone.now()
            pending.password_hash = pending.code_hash = pending.encrypted_code = ""
            pending.save()
            audit(user, "account.registered", user)
    if wrong_code:
        raise ValidationError({"code": "Неверный код подтверждения"})
    return user
