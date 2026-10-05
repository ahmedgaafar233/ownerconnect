from django.urls import reverse
from rest_framework import serializers

from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = (
            "id",
            "kind",
            "title",
            "body",
            "price",
            "contact_phone",
            "event_date",
            "image_url",
            "published_at",
        )
        read_only_fields = fields

    def get_image_url(self, obj: Announcement):
        if not obj.image:
            return None
        request = self.context.get("request")
        path = reverse("announcements:image", args=[obj.id])
        return request.build_absolute_uri(path) if request else path
