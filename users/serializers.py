from rest_framework import serializers
from core.models import Unit, OwnerUnit
from .models import User, ActivationCode, MobileDevice
from .services import UserService


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ("id", "unit_key", "building_no", "unit_no", "is_active")


class MeSerializer(serializers.ModelSerializer):
    units = serializers.SerializerMethodField()
    resort_name = serializers.SerializerMethodField()
    resort_logo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "phone", "fullname", "role", "resort", "resort_name", "resort_logo_url", "units")

    def get_resort_name(self, obj: User):
        return obj.resort.name if obj.resort_id else None

    def get_resort_logo_url(self, obj: User):
        if not obj.resort_id or not obj.resort.logo:
            return None
        request = self.context.get("request")
        url = obj.resort.logo.url
        return request.build_absolute_uri(url) if request else url

    def get_units(self, obj: User):
        if obj.role not in (User.Role.OWNER, User.Role.TENANT):
            return []
        unit_ids = OwnerUnit.objects.filter(owner=obj).values_list("unit_id", flat=True)
        qs = Unit.objects.filter(id__in=unit_ids, is_active=True).order_by("unit_key")
        return UnitSerializer(qs, many=True).data


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("fullname",)


class FirebaseAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True, help_text="Firebase Auth ID Token")
    # Only needed the first time a Google/Email-Password sign-in links to a
    # staff-pre-provisioned owner (see FirebaseAuthView). Phone-OTP sign-in
    # ignores these entirely.
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    code = serializers.CharField(required=False, allow_blank=True, max_length=6, default="")


class FCMTokenRegisterSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(required=True, help_text="FCM Device Token")
    device_id = serializers.CharField(required=False, allow_blank=True, default="")
    os = serializers.CharField(required=False, allow_blank=True, default="")


class ActivateSerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField(max_length=6)

    def validate(self, attrs):
        try:
            activation = UserService.validate_activation_code(attrs["phone"], attrs["code"])
        except ValueError as e:
            raise serializers.ValidationError(str(e))

        attrs["user"] = activation.user
        attrs["activation"] = activation
        return attrs


class GenerateCodeSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value):
        phone = value.strip()
        if not User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("User not found")
        return phone