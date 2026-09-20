from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Resort
from .serializers import ResortPickerSerializer


class ResortListView(generics.ListAPIView):
    """
    Public, unauthenticated — lets the mobile app show a "pick your resort"
    screen before login. See ResortPickerSerializer for why this is safe.
    """
    permission_classes = [AllowAny]
    serializer_class = ResortPickerSerializer
    pagination_class = None

    def get_queryset(self):
        return Resort.objects.filter(is_active=True).order_by("name")
