from django.urls import reverse
from rest_framework import serializers
from .models import Ticket, Message, VisitorPass
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
        fields = ("unit", "category", "priority", "subject", "description")

    def validate_unit(self, value):
        user = self.context["request"].user
        if user.role in ("OWNER", "TENANT"):
            owns = value.owner_units.filter(owner=user).exists()
            if not owns:
                raise serializers.ValidationError("You do not own this unit.")
        return value


class VisitorPassSerializer(serializers.ModelSerializer):
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    resort_name = serializers.CharField(source="resort.name", read_only=True)

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
            "status",
            "created_at",
        )
        read_only_fields = ("id", "pass_code", "status", "created_at")

    def validate_unit(self, value):
        user = self.context["request"].user
        if user.role in ("OWNER", "TENANT"):
            owns = value.owner_units.filter(owner=user).exists()
            if not owns:
                raise serializers.ValidationError("You do not own this unit.")
        return value
