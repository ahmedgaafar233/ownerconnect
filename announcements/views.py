from django.http import FileResponse, Http404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from users.models import User

from .models import Announcement
from .serializers import AnnouncementSerializer


class AnnouncementPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 100


def _visible_for(request):
    """
    The announcements this request may see: its own resort's, published and
    unexpired. request.tenant is what TenantMiddleware resolved for the
    caller — for an owner that is only ever a resort they actually hold a
    unit in, never a client-supplied id.
    """
    if request.user.role not in (User.Role.OWNER, User.Role.TENANT):
        raise PermissionDenied("Residents only")
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return Announcement.objects.none()
    return Announcement.objects.visible().filter(resort=tenant)


class AnnouncementListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnouncementSerializer
    pagination_class = AnnouncementPagination

    def get_queryset(self):
        qs = _visible_for(self.request)
        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        return qs


class AnnouncementImageView(APIView):
    """
    Streams an announcement's image after the same resort/visibility check
    as the list — see PaymentReceiptDownloadView for why media isn't served
    as a bare public file.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        announcement = _visible_for(request).filter(pk=pk).first()
        if announcement is None or not announcement.image:
            raise Http404
        return FileResponse(announcement.image.open("rb"))
