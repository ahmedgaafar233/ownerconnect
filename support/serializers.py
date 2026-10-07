from datetime import datetime, time

from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers
from .models import Message, PassScan, Ticket, VisitorPass
from core.models import Unit


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.fullname", read_only=True)
    sender_phone = serializers.CharField(source="sender.phone", read_only=True)

    class Meta:
        model = Message
        fields = (
            "id",
            "ticket",
            "sender",
            "sender_name",
            "sender_phone",
            "message_type",
            "content",
            "attachment",
            "attachment_name",
            "is_read",
            "created_at",
        )
        read_only_fields = ("id", "sender", "created_at")

    def to_representation(self, instance):
        # Uploads still go through the plain `attachment` FileField above —
        # only the outgoing URL is swapped, to the authenticated download
        # view rather than the raw /media/ path (see
        # TicketAttachmentDownloadView).
        data = super().to_representation(instance)
        if instance.attachment:
            request = self.context.get("request")
            path = reverse("support:ticket_attachment_download", args=[instance.id])
            data["attachment"] = request.build_absolute_uri(path) if request else path
        else:
            data["attachment"] = None
        return data


class TicketSerializer(serializers.ModelSerializer):
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    resort_name = serializers.CharField(source="resort.name", read_only=True)
    owner_phone = serializers.CharField(source="owner.phone", read_only=True)
    messages_count = serializers.IntegerField(source="messages.count", read_only=True)
    latest_message = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = (
            "id",
            "mobile_ticket_id",
            "unit",
            "unit_key",
            "resort",
            "resort_name",
            "owner",
            "owner_phone",
            "category",
            "service_type",
            "priority",
            "subject",
            "description",
            "status",
            "assigned_to",
            "resolution_notes",
            "is_overdue",
            "messages_count",
            "latest_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "mobile_ticket_id",
            "owner",
            "resort",
            "assigned_to",
            "created_at",
            "updated_at",
        )

    def get_latest_message(self, obj):
        latest = obj.messages.order_by("-created_at").first()
        if latest:
            return MessageSerializer(latest).data
        return None


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("unit", "category", "service_type", "priority", "subject", "description")

    def validate_unit(self, value):
        user = self.context["request"].user
        if user.role in ("OWNER", "TENANT"):
            from core.leases import has_unit_access

            if not value.owner_units.filter(owner=user).exists():
                raise serializers.ValidationError("You do not own this unit.")
            if not has_unit_access(user, value):
                raise serializers.ValidationError(
                    "Your rental of this unit has ended, so you can no longer make requests for it."
                )
        return value


class VisitorPassSerializer(serializers.ModelSerializer):
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    resort_name = serializers.CharField(source="resort.name", read_only=True)
    # Calendar dates in the RESORT's time zone, as an alternative to exact
    # instants: "the 10th" means the same day whatever time zone the owner's
    # phone is in, and the server — not the phone — turns it into a window.
    start_date = serializers.DateField(write_only=True, required=False)
    end_date = serializers.DateField(write_only=True, required=False)

    class Meta:
        model = VisitorPass
        fields = (
            "id",
            "pass_code",
            "unit",
            "unit_key",
            "resort",
            "resort_name",
            "pass_type",
            "visitor_name",
            "national_id_or_passport",
            "car_plate",
            "valid_from",
            "valid_to",
            "start_date",
            "end_date",
            "status",
            "rejection_reason",
            "decided_at",
            "created_at",
        )
        # resort is derived from the unit in VisitorPassListCreateView.perform_create;
        # as a required writable field every create without it was a 400.
        read_only_fields = ("id", "pass_code", "resort", "status", "created_at", "rejection_reason", "decided_at")

    def validate_unit(self, value):
        user = self.context["request"].user
        if user.role in ("OWNER", "TENANT"):
            from core.leases import has_unit_access

            if not value.owner_units.filter(owner=user).exists():
                raise serializers.ValidationError("You do not own this unit.")
            if not has_unit_access(user, value):
                raise serializers.ValidationError(
                    "Your rental of this unit has ended, so you can no longer make requests for it."
                )
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Either exact instants or start_date/end_date — enforced in validate().
        self.fields["valid_from"].required = False
        self.fields["valid_to"].required = False

    def validate(self, attrs):
        start_date, end_date = attrs.pop("start_date", None), attrs.pop("end_date", None)
        if start_date:
            tz = timezone.get_current_timezone()
            attrs["valid_from"] = timezone.make_aware(datetime.combine(start_date, time.min), tz)
            attrs["valid_to"] = timezone.make_aware(datetime.combine(end_date or start_date, time(23, 59, 59)), tz)
            if (end_date or start_date) < timezone.localdate():
                raise serializers.ValidationError({"end_date": ["That date has already passed."]})
        valid_from, valid_to = attrs.get("valid_from"), attrs.get("valid_to")
        if not (valid_from and valid_to):
            raise serializers.ValidationError("Give start_date (and end_date), or valid_from and valid_to.")
        if valid_from and valid_to:
            if valid_to <= valid_from:
                raise serializers.ValidationError({"valid_to": ["The pass must end after it starts."]})
            # A visit is a day trip: staying overnight is a rental, which is
            # not something a visitor pass covers. (Cards are a date range.)
            if (
                attrs.get("pass_type", VisitorPass.PassType.VISITOR) == VisitorPass.PassType.VISITOR
                and timezone.localdate(valid_from) != timezone.localdate(valid_to)
            ):
                raise serializers.ValidationError({
                    "valid_to": ["A visitor pass covers a single day — overnight stays are rentals, not visits."]
                })
        return attrs


class PassRequestSerializer(serializers.ModelSerializer):
    """What Security sees when reviewing a pass request."""
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    requested_by_role = serializers.CharField(source="owner.role", read_only=True)
    requested_by_phone = serializers.CharField(source="owner.phone", read_only=True)
    unit_card_allowance = serializers.SerializerMethodField()
    unit_cards_in_use = serializers.SerializerMethodField()
    unit_lease = serializers.SerializerMethodField()

    class Meta:
        model = VisitorPass
        fields = (
            "id", "pass_type", "visitor_name", "national_id_or_passport", "car_plate",
            "valid_from", "valid_to", "status", "rejection_reason", "decided_at", "created_at",
            "unit_key", "requested_by_name", "requested_by_role", "requested_by_phone",
            "unit_card_allowance", "unit_cards_in_use", "unit_lease",
        )
        read_only_fields = fields

    def get_requested_by_name(self, obj):
        return obj.owner.fullname or ""

    def get_unit_card_allowance(self, obj):
        return obj.unit.card_allowance

    def get_unit_cards_in_use(self, obj):
        return VisitorPass.active_cards(obj.unit).count()

    def get_unit_lease(self, obj):
        """
        The tenant the owner registered for this unit, so Security can approve
        card requests knowing the unit is rented (the owner told the village
        about the tenant when registering — there's no separate approval step).
        """
        from core.leases import current_lease

        lease = current_lease(obj.unit)
        if lease is None:
            return None
        return {
            "tenant_name": lease.tenant_name,
            "tenant_phone": lease.tenant_phone,
            "term": lease.term,
            "start_date": lease.start_date,
            "end_date": lease.end_date,
            "occupants": lease.occupants,
        }


class PassRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class PassScanRequestSerializer(serializers.Serializer):
    pass_code = serializers.CharField(max_length=64)
    towels_issued = serializers.IntegerField(min_value=0, max_value=20, required=False, default=0)
    device_label = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")

    def validate_pass_code(self, value):
        # A phone camera and a handheld/USB scanner (which types the code as
        # keystrokes, often with a trailing Enter/Tab and sometimes lowercase)
        # must resolve to the same pass. CharField already trims the ends.
        return value.upper()


class ScannedPassSerializer(serializers.ModelSerializer):
    """
    What a scanner screen needs to decide on the spot: whose pass it is and
    whether the holder is a resident or a visitor. The gate additionally gets
    the visitor's ID and the issuing resident's phone (to call and confirm);
    beach/pool staff don't need either, so they never receive them.
    """
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    issued_by_name = serializers.SerializerMethodField()
    issued_by_role = serializers.CharField(source="owner.role", read_only=True)

    class Meta:
        model = VisitorPass
        fields = (
            "pass_type", "visitor_name", "car_plate", "valid_from", "valid_to",
            "status", "unit_key", "issued_by_name", "issued_by_role",
        )

    def get_issued_by_name(self, obj):
        return obj.owner.fullname or ""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get("point") == PassScan.Point.GATE:
            data["national_id_or_passport"] = instance.national_id_or_passport
            data["issued_by_phone"] = instance.owner.phone
        return data


class PassScanSerializer(serializers.ModelSerializer):
    visitor_name = serializers.CharField(source="visitor_pass.visitor_name", default="", read_only=True)
    pass_type = serializers.CharField(source="visitor_pass.pass_type", default="", read_only=True)
    unit_key = serializers.CharField(source="visitor_pass.unit.unit_key", default="", read_only=True)

    class Meta:
        model = PassScan
        fields = (
            "id", "pass_code", "point", "result", "deny_reason", "towels_issued",
            "scanned_at", "visitor_name", "pass_type", "unit_key",
        )
        read_only_fields = fields
