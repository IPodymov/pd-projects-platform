from django.db import connection
from django.conf import settings
from django.http import JsonResponse
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from .models import Notification


def live(request):
    return JsonResponse({"status": "ok"})


def ready(request):
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        import redis

        redis.Redis.from_url(
            settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2
        ).ping()
    except Exception:
        return JsonResponse({"status": "not_ready"}, status=503)
    return JsonResponse({"status": "ready"})


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "kind",
            "target",
            "delivery_status",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NotificationSerializer.Meta.model.objects.none()
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by(
            "-created_at"
        )

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        n = self.get_object()
        Notification.objects.filter(pk=n.pk, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        n.refresh_from_db()
        return Response(NotificationSerializer(n).data)
