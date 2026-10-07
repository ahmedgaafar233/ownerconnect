from django.utils import timezone
from rest_framework import serializers
from core.models import Lease, Unit, OwnerUnit
from .models import User, ActivationCode, MobileDevice
from .services import UserService


class UnitSerializer(serializers.ModelSerializer):
    # card_allowance is null for a unit with no type assigned (unrestricted);
    # cards_used lets the pass form show "2 of 3 used" before the owner submits.
    card_allowance = serializers.IntegerField(read_only=True, allow_null=True)
    cards_used = serializers.SerializerMethodField()
    unit_type_name = serializers.SerializerMethodField()
    # How the signed-in person relates to this unit, and its rental (if any).
    relation = serializers.SerializerMethodField()
    lease = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = (
            "id", "unit_key", "building_no", "unit_no", "is_active", "card_allowance", "cards_used",
            "unit_type_name", "relation", "lease",
        )

    def get_cards_used(self, obj: Unit) -> int:
        from support.models import VisitorPass
        return VisitorPass.active_cards(obj).count()

    def get_unit_type_name(self, obj: Unit):
        return obj.unit_type.name if obj.unit_type_id else None

    def _user(self):
        return self.context.get("user")

    def get_relation(self, obj: Unit):
        user = self._user()
        return None if user is None else ("TENANT" if user.role == User.Role.TENANT else "OWNER")

    def get_lease(self, obj: Unit):
        """
        For an owner: the rental running (or next coming up) on the unit, with
        the tenant's contact details and how much of their own months they
        still owe — or, when none is running, the last long-term one if it
        ended recently or its tenant still owes. For a tenant: just their own
        lease window.
        """
        user = self._user()
        if user is None:
            return None
        today = timezone.localdate()

        if user.role == User.Role.TENANT:
            link = OwnerUnit.objects.filter(owner=user, unit=obj).first()
            if link is None or not (link.lease_start_date or link.lease_end_date):
                return None
            end = link.lease_end_date
            from core.leases import lease_meter_summary

            mine = (
                Lease.objects.filter(unit=obj, tenant=user, cancelled_at__isnull=True)
                .order_by("-start_date")
                .first()
            )
            return {
                "status": "ENDED" if end and end < today else "ACTIVE",
                "start_date": link.lease_start_date,
                "end_date": end,
                "meter_readings": lease_meter_summary(mine) if mine else None,
            }

        from core.lease_api import LeaseSerializer

        mine = Lease.objects.filter(unit=obj, landlord=user, cancelled_at__isnull=True)
        lease = mine.filter(end_date__gte=today).order_by("start_date").first()
        if lease is None:
            lease = self._recently_ended(mine, today)
        return LeaseSerializer(lease).data if lease else None

    # How long an ended long-term rental stays on the unit's card once its
    # tenant has settled up (until then it stays: the owner needs to see that
    # the tenant is cleared before handing back a deposit).
    RECENT_DAYS = 90

    def _recently_ended(self, mine, today):
        from datetime import timedelta

        from billing.lease_rules import tenant_balance

        ended = mine.filter(term=Lease.Term.LONG, end_date__lt=today).order_by("-end_date")[:5]
        for lease in ended:
            if lease.end_date >= today - timedelta(days=self.RECENT_DAYS) or tenant_balance(lease) > 0:
                return lease
        return None


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
        qs = Unit.objects.filter(id__in=unit_ids, is_active=True).select_related("unit_type").order_by("unit_key")
        return UnitSerializer(qs, many=True, context={"user": obj}).data


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