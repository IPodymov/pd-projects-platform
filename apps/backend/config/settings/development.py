from .base import *

DEBUG = True
# Development can only use the local mail catcher, regardless of SMTP variables.
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {"host": "mailpit", "port": 1025, "timeout": 15},
    }
}
