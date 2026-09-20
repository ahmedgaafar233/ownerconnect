from rest_framework import serializers

from .models import Notification, Resort


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "type", "title", "body", "data", "is_read", "created_at"]


class ResortPickerSerializer(serializers.ModelSerializer):
    """
    Deliberately minimal and public (no auth) — a resort's name/logo is
    branding, not tenant data, and the owner needs to pick their resort
    before they've signed in. Never add anything here that isn't already
    equally public on the resort's own marketing/signage.
    """
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Resort
        fields = ("id", "name", "logo_url")

    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url
