from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework.views import exception_handler as drf_handler
from rest_framework.exceptions import (
    ValidationError,
    APIException,
    NotAuthenticated,
    AuthenticationFailed,
)
from rest_framework import serializers, viewsets


class BusinessError(APIException):
    status_code = 409
    default_code = "business_conflict"

    def __init__(self, detail, code="business_conflict", status=409):
        self.status_code = status
        self.business_code = code
        super().__init__(detail, code)


def check_revision(obj, expected=None, required=False):
    if required and not expected:
        raise BusinessError(
            "Обновите данные перед сохранением", "revision_required", 428
        )
    from django.utils.dateparse import parse_datetime

    try:
        stamp = parse_datetime(expected.strip('"')) if expected else None
    except ValueError:
        stamp = None
    if expected and stamp != obj.updated_at:
        raise BusinessError(
            "Данные изменены другим участником. Обновите запись; ваш ввод сохранён.",
            "stale_revision",
        )


class RevisionSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        request = self.context.get("request")
        if request and request.path.startswith("/api/v1/"):
            forbidden = set(data) - set(self.fields)
            forbidden |= {
                key for key in data if key in self.fields and self.fields[key].read_only
            }
            if forbidden:
                raise ValidationError(
                    {
                        key: "Поле задаётся сервером или изменяется отдельным действием"
                        for key in forbidden
                    }
                )
        return super().to_internal_value(data)

    def get_fields(self):
        fields = super().get_fields()
        if hasattr(self.Meta.model, "updated_at"):
            fields["updated_at"] = serializers.DateTimeField(read_only=True)
        return fields


class RevisionActionMixin:
    def get_object(self):
        obj = super().get_object()
        request = self.request
        if (
            request.method == "POST"
            and request.path.startswith("/api/v1/")
            and self.action
            in {
                "transition",
                "review",
                "send",
                "change",
                "change_series",
                "cancel",
                "set_active",
                "transfer",
                "attendance",
                "decide",
                "correct_email",
                "revoke",
                "reissue",
                "publish",
                "approve",
            }
        ):
            check_revision(obj, request.headers.get("If-Match"), required=True)
        return obj


class RevisionReadOnlyViewSet(RevisionActionMixin, viewsets.ReadOnlyModelViewSet):
    pass


class GuardedModelViewSet(RevisionActionMixin, viewsets.ModelViewSet):
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404

        queryset = self.get_queryset()
        if not getattr(self, "business_update", False):
            queryset = queryset.select_for_update(of=("self",))
        obj = get_object_or_404(queryset, pk=kwargs["pk"])
        self.check_object_permissions(request, obj)
        check_revision(
            obj, request.headers.get("If-Match"), request.path.startswith("/api/v1/")
        )
        self._locked_object = obj
        return super().update(request, *args, **kwargs)

    def get_object(self):
        if hasattr(self, "_locked_object"):
            return self._locked_object
        return super().get_object()


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(getattr(exc, "message_dict", None) or exc.messages)
    if isinstance(exc, IntegrityError):
        exc = BusinessError(
            "Конфликт с существующими данными", "duplicate_or_invalid_relation"
        )
    response = drf_handler(exc, context)
    if response is not None:
        if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            response.status_code = 401
        original = response.data
        fields = (
            original if isinstance(original, dict) and "detail" not in original else {}
        )
        detail = (
            original.get("detail", "Проверьте поля формы")
            if isinstance(original, dict)
            else " · ".join(str(item) for item in original)
            if isinstance(original, (list, tuple))
            else str(original)
        )
        response.data = {
            "code": getattr(
                exc, "business_code", getattr(exc, "default_code", "request_error")
            ),
            "detail": detail,
            "fields": fields,
            "status": response.status_code,
            "error": original,
        }
    return response


def schema_v1(endpoints, **kwargs):
    return [entry for entry in endpoints if entry[0].startswith("/api/v1/")]
