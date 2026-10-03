from django.core.checks import register, Error
from django.core.mail import get_connection


@register()
def mail_configuration(app_configs, **kwargs):
    try:
        get_connection()
    except Exception as exc:
        return [Error(str(exc), id="platform.E001")]
    return []
