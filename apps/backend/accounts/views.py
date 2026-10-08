from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import serializers
from drf_spectacular.utils import extend_schema
from .models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class SessionSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    csrf = serializers.CharField()
    platform_admin = serializers.BooleanField()
    roles = serializers.ListField(child=serializers.CharField())


class SessionView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=SessionSerializer)
    def get(self, request):
        u = request.user
        roles = []
        if u.is_authenticated:
            roles = list(
                u.staffassignment_set.filter(active=True)
                .values_list("role", flat=True)
                .distinct()
            )
        return Response(
            {
                "id": u.pk if u.is_authenticated else None,
                "name": u.get_full_name() if u.is_authenticated else "",
                "email": u.email if u.is_authenticated else "",
                "csrf": get_token(request),
                "platform_admin": u.is_superuser,
                "roles": roles,
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses=SessionSerializer)
    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        u = User.objects.filter(email__iexact=s.validated_data["email"]).first()
        user = authenticate(
            request,
            username=u.username if u else "",
            password=s.validated_data["password"],
        )
        if not user:
            raise AuthenticationFailed("Неверная почта или пароль")
        login(request, user)
        from .models import LoginEvent

        LoginEvent.objects.create(user=user)
        return SessionView().get(request)


class LogoutView(APIView):
    @extend_schema(request=None, responses=None)
    def post(self, request):
        logout(request)
        return Response(status=204)


class EmailChangeRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class EmailChangeConfirmationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$")


class EmailChangeResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    detail = serializers.CharField()


class EmailChangeRequestView(APIView):
    @extend_schema(
        request=EmailChangeRequestSerializer, responses=EmailChangeResponseSerializer
    )
    def post(self, request):
        from .services import request_email_change

        s = EmailChangeRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        change = request_email_change(
            request.user, s.validated_data["email"], s.validated_data["password"]
        )
        return Response({"id": change.pk, "detail": "Код отправлен на новую почту"})


class EmailChangeConfirmView(APIView):
    @extend_schema(
        request=EmailChangeConfirmationSerializer, responses=SessionSerializer
    )
    def post(self, request):
        from .services import confirm_email_change

        s = EmailChangeConfirmationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = confirm_email_change(
            request.user, s.validated_data["id"], s.validated_data["code"]
        )
        request.user = user
        return SessionView().get(request)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["display_name", "date_of_birth"]


class ProfileUpdateSerializer(ProfileSerializer):
    password = serializers.CharField(write_only=True)

    class Meta(ProfileSerializer.Meta):
        fields = [*ProfileSerializer.Meta.fields, "password"]

    def validate_date_of_birth(self, value):
        from django.utils import timezone

        if value and (
            value > timezone.localdate() or value.year < timezone.localdate().year - 120
        ):
            raise serializers.ValidationError("Укажите действительную дату рождения")
        return value


class ProfileView(APIView):
    @extend_schema(responses=ProfileSerializer)
    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    @extend_schema(request=ProfileUpdateSerializer, responses=ProfileSerializer)
    def post(self, request):
        from django.db import transaction
        from common.services import audit

        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            s = ProfileUpdateSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            if not user.check_password(s.validated_data.pop("password")):
                raise AuthenticationFailed("Подтвердите текущий пароль")
            for key, value in s.validated_data.items():
                setattr(user, key, value)
            user.save()
            audit(
                user,
                "account.profile_changed",
                user,
                details={"fields": list(s.validated_data)},
            )
        return Response(ProfileSerializer(user).data)


class RegistrationInputSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, max_length=128, trim_whitespace=False
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    def validate_date_of_birth(self, value):
        return ProfileUpdateSerializer().validate_date_of_birth(value)

    def validate(self, data):
        forbidden = set(self.initial_data) - set(self.fields)
        if forbidden:
            raise serializers.ValidationError(
                {key: "Поле недоступно при регистрации" for key in forbidden}
            )
        return data


@method_decorator(csrf_protect, name="dispatch")
class RegistrationRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=RegistrationInputSerializer, responses=EmailChangeResponseSerializer
    )
    def post(self, request):
        from .registration import request_registration

        if request.user.is_authenticated:
            raise serializers.ValidationError("Вы уже вошли в аккаунт")
        s = RegistrationInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        pending = request_registration(s.validated_data)
        return Response(
            {"id": pending.pk, "detail": "Код отправлен на вашу почту"}, status=202
        )


@method_decorator(csrf_protect, name="dispatch")
class RegistrationConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=EmailChangeConfirmationSerializer, responses=SessionSerializer
    )
    def post(self, request):
        from .registration import confirm_registration

        if request.user.is_authenticated:
            raise serializers.ValidationError("Вы уже вошли в аккаунт")
        s = EmailChangeConfirmationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = confirm_registration(s.validated_data["id"], s.validated_data["code"])
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        from .models import LoginEvent

        LoginEvent.objects.create(user=user)
        return SessionView().get(request)
