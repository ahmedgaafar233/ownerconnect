from rest_framework import serializers
from django.utils import timezone
from core.models import Unit, OwnerUnit
from .models import User, ActivationCode


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ("id", "unit_key", "building_no", "unit_no", "is_active")


class MeSerializer(serializers.ModelSerializer):
    units = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "phone", "role", "resort", "units")

    def get_units(self, obj: User):
        if obj.role != User.Role.OWNER:
            return []
        unit_ids = OwnerUnit.objects.filter(owner=obj).values_list("unit_id", flat=True)
        qs = Unit.objects.filter(id__in=unit_ids, is_active=True).order_by("unit_key")
        return UnitSerializer(qs, many=True).data


class ActivateSerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField(max_length=6)

    def validate(self, attrs):
        phone = attrs["phone"].strip()
        code = attrs["code"].strip()

        try:
            user = User.objects.get(phone=phone, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid phone/code")

        activation = (
            ActivationCode.objects
            .filter(user=user, code=code, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not activation:
            raise serializers.ValidationError("Invalid phone/code")

        if activation.expires_at and activation.expires_at < timezone.now():
            raise serializers.ValidationError("Code expired")

        attrs["user"] = user
        attrs["activation"] = activation
        return attrs


class GenerateCodeSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value):
        phone = value.strip()
        if not User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("User not found")
        return phone