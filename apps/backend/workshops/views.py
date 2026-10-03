from common.api import RevisionReadOnlyViewSet, RevisionSerializer, GuardedModelViewSet
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from drf_spectacular.utils import extend_schema
from django.db.models import Q
from accounts.models import User
from institutions.models import Institution
from common.access import require_institution, institution_ids
from .models import Workshop, Registration, Partnership, Subscription, GroupApplication
from .services import (
    visible,
    register,
    cancel,
    announce,
    update_workshop,
    close_workshop,
    cancel_group,
    record_attendance,
    validate_workshop,
)


class WorkshopStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["cancelled", "completed"])


class WorkshopSerializer(RevisionSerializer):
    available = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)

    def to_representation(self, obj):
        data = super().to_representation(obj)
        request = self.context.get("request")
        user = request.user if request else None
        if not user or not (
            user.is_superuser
            or user.pk in (obj.organizer_id, obj.leader_id)
            or obj.registrations.filter(user=user, status="confirmed").exists()
        ):
            data["online_url"] = ""
        return data

    def get_available(self, obj) -> int:
        return max(
            0, obj.capacity - obj.registrations.filter(status="confirmed").count()
        )

    class Meta:
        model = Workshop
        fields = [
            "id",
            "university",
            "organizer",
            "title",
            "description",
            "topic",
            "min_age",
            "max_age",
            "requirements",
            "starts_at",
            "ends_at",
            "format",
            "location",
            "capacity",
            "registration_opens_at",
            "registration_closes_at",
            "audience",
            "schools",
            "published",
            "available",
            "status",
            "leader",
            "online_url",
        ]
        read_only_fields = ["organizer", "published"]


class RegistrationSerializer(RevisionSerializer):
    class Meta:
        model = Registration
        fields = ["id", "workshop", "user", "group", "status", "attended"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    users = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), many=True, required=False
    )
    school = serializers.PrimaryKeyRelatedField(
        queryset=Institution.objects.all(), required=False
    )


class PartnershipSerializer(RevisionSerializer):
    class Meta:
        model = Partnership
        fields = ["id", "university", "school", "status", "starts_on", "ends_on"]
        read_only_fields = ["status"]

    def validate(self, data):
        if (
            data["university"].kind != "university"
            or data["school"].kind != "school"
            or data["starts_on"] > data["ends_on"]
        ):
            raise ValidationError("Неверные стороны или даты партнёрства")
        return data


class SubscriptionSerializer(RevisionSerializer):
    class Meta:
        model = Subscription
        fields = ["id", "school", "email_enabled"]


class WorkshopAttendanceSerializer(serializers.Serializer):
    attended = serializers.BooleanField()


class WorkshopViewSet(GuardedModelViewSet):
    business_update = True
    queryset = WorkshopSerializer.Meta.model.objects.none()
    serializer_class = WorkshopSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return visible(self.request.user)

    def perform_create(self, s):
        require_institution(
            self.request.user, s.validated_data["university"], ["organizer", "admin"]
        )
        values = {k: v for k, v in s.validated_data.items() if k != "schools"}
        validate_workshop(Workshop(organizer=self.request.user, **values))
        s.instance = s.save(organizer=self.request.user)
        if s.instance.university.kind != "university":
            s.instance.delete()
            raise ValidationError("Требуется вуз")

    def perform_update(self, s):
        s.instance = update_workshop(
            self.request.user,
            s.instance,
            dict(s.validated_data),
            self.request.headers.get("If-Match"),
        )

    @extend_schema(
        request=RegisterSerializer, responses=RegistrationSerializer(many=True)
    )
    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(
            RegistrationSerializer(
                register(request.user, self.get_object(), **s.validated_data), many=True
            ).data
        )

    @extend_schema(request=None, responses=WorkshopSerializer)
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        obj = self.get_object()
        announce(request.user, obj, request.headers.get("If-Match"))
        return Response(WorkshopSerializer(obj).data)

    @extend_schema(request=WorkshopStatusSerializer, responses=WorkshopSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        data = WorkshopStatusSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(
            WorkshopSerializer(
                close_workshop(
                    request.user,
                    self.get_object(),
                    data.validated_data["status"],
                    request.headers.get("If-Match"),
                )
            ).data
        )


class RegistrationViewSet(RevisionReadOnlyViewSet):
    queryset = RegistrationSerializer.Meta.model.objects.none()
    serializer_class = RegistrationSerializer

    def get_queryset(self):
        u = self.request.user
        if u.is_superuser:
            return Registration.objects.all()
        from common.access import classrooms

        return Registration.objects.filter(
            Q(user=u)
            | Q(workshop__organizer=u)
            | Q(workshop__leader=u)
            | Q(
                group__responsible=u,
                user__studentmembership__classroom__in=classrooms(u, True),
            )
        ).distinct()

    @extend_schema(request=None, responses=RegistrationSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return Response(
            RegistrationSerializer(
                cancel(request.user, self.get_object(), request.headers.get("If-Match"))
            ).data
        )

    @extend_schema(
        request=WorkshopAttendanceSerializer, responses=RegistrationSerializer
    )
    @action(detail=True, methods=["post"])
    def attendance(self, request, pk=None):
        obj = self.get_object()
        if not request.user.is_superuser and request.user.pk not in (
            obj.workshop.organizer_id,
            obj.workshop.leader_id,
        ):
            raise PermissionDenied("Только организатор")
        s = WorkshopAttendanceSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        obj = record_attendance(
            request.user,
            obj,
            s.validated_data["attended"],
            request.headers.get("If-Match"),
        )
        return Response(RegistrationSerializer(obj).data)


class PartnershipTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["active", "ended"])


class PartnershipViewSet(GuardedModelViewSet):
    queryset = PartnershipSerializer.Meta.model.objects.none()
    serializer_class = PartnershipSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Partnership.objects.filter(
            Q(university_id__in=institution_ids(self.request.user))
            | Q(school_id__in=institution_ids(self.request.user))
        )

    def perform_create(self, s):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Партнёрства утверждает администратор платформы")
        obj = s.save(status="pending")
        from common.services import audit

        audit(self.request.user, "partnership.created", obj, obj.university)

    @extend_schema(
        request=PartnershipTransitionSerializer, responses=PartnershipSerializer
    )
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        from .services import transition_partnership

        data = PartnershipTransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(
            self.get_serializer(
                transition_partnership(
                    request.user,
                    self.get_object(),
                    data.validated_data["status"],
                    request.headers.get("If-Match"),
                )
            ).data
        )


class SubscriptionViewSet(GuardedModelViewSet):
    queryset = SubscriptionSerializer.Meta.model.objects.none()
    serializer_class = SubscriptionSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)

    def perform_create(self, s):
        require_institution(
            self.request.user,
            s.validated_data["school"],
            ["admin", "curator", "teacher"],
        )
        s.save(user=self.request.user)

    def perform_update(self, s):
        if (
            "school" in s.validated_data
            and s.validated_data["school"] != s.instance.school
        ):
            raise ValidationError("Школа подписки неизменяема")
        s.save()


class GroupSerializer(RevisionSerializer):
    confirmed = serializers.SerializerMethodField()
    waiting = serializers.SerializerMethodField()
    participants = RegistrationSerializer(
        source="registration_set", many=True, read_only=True
    )

    def get_confirmed(self, obj) -> int:
        return obj.registration_set.filter(status="confirmed").count()

    def get_waiting(self, obj) -> int:
        return obj.registration_set.filter(status="waiting").count()

    class Meta:
        model = GroupApplication
        fields = [
            "id",
            "workshop",
            "school",
            "responsible",
            "status",
            "confirmed",
            "waiting",
            "participants",
        ]
        read_only_fields = fields


class GroupViewSet(RevisionReadOnlyViewSet):
    queryset = GroupApplication.objects.none()
    serializer_class = GroupSerializer

    def get_queryset(self):
        u = self.request.user
        if u.is_superuser:
            return GroupApplication.objects.all()
        return GroupApplication.objects.filter(
            Q(responsible=u, school_id__in=institution_ids(u))
            | Q(workshop__organizer=u)
            | Q(workshop__leader=u)
        )

    @extend_schema(request=None, responses=GroupSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return Response(
            GroupSerializer(
                cancel_group(
                    request.user, self.get_object(), request.headers.get("If-Match")
                )
            ).data
        )
