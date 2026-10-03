from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import BaseFilterBackend


class VersionedPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        if not request.path.startswith("/api/v1/"):
            return None
        return super().paginate_queryset(
            queryset.order_by("pk") if not queryset.ordered else queryset, request, view
        )


class AllowedFilters(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        fields = {f.name: f for f in queryset.model._meta.fields}
        search = request.query_params.get("search", "").strip()
        if len(search) > 100:
            raise ValidationError({"search": "Максимум 100 символов"})
        if search:
            from django.db.models import Q

            scope = Q()
            for name in ("title", "name", "full_name"):
                if name in fields:
                    scope |= Q(**{name + "__icontains": search})
            if scope:
                queryset = queryset.filter(scope)
        for name in (
            "institution",
            "classroom",
            "course",
            "project",
            "lesson",
            "status",
            "teacher",
            "document",
        ):
            value = request.query_params.get(name)
            if value and name in fields:
                try:
                    field = fields[name]
                    value = (
                        field.target_field if field.is_relation else field
                    ).to_python(value)
                    queryset = queryset.filter(**{name: value})
                except ValueError, DjangoValidationError:
                    raise ValidationError({name: "Некорректный фильтр"})
        return queryset
