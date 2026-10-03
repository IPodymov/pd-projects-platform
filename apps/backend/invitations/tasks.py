from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Invitation
from .services import cipher, invitation_url, expire


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_invitation(pk, encrypted_code=""):
    expire()
    invite = Invitation.objects.get(pk=pk)
    if invite.status != "pending":
        return
    from common.access import require_class, require_institution
    from rest_framework.exceptions import PermissionDenied

    if invite.issued_by_id:
        try:
            if invite.role == "student":
                require_class(invite.issued_by, invite.classroom, True)
            else:
                require_institution(invite.issued_by, invite.institution, ["admin"])
        except PermissionDenied:
            return
    if encrypted_code:
        import hmac
        from .services import code_digest

        code = cipher().decrypt(encrypted_code.encode()).decode()
        if not hmac.compare_digest(invite.code_hash, code_digest(invite, code)):
            return
        message = "Код подтверждения: " + code + "\nДействует 10 минут."
    else:
        message = (
            "Примите приглашение: "
            + invitation_url(invite)
            + "\nДля регистрации потребуется подтвердить почту."
        )
    send_mail(
        "Приглашение: Инженеры будущего",
        message,
        settings.DEFAULT_FROM_EMAIL,
        [invite.email],
    )


@shared_task
def expire_invitations():
    from accounts.models import EmailChange
    from django.utils import timezone

    EmailChange.objects.filter(expires_at__lte=timezone.now()).update(
        encrypted_code="", code_hash=""
    )
    return expire()
