"""
What the village's Security staff see of the tenancies in their village: who is
renting each unit, every adult staying there, and the papers the owner sent —
the ID photos, marriage certificate, passports — so they can register them and
recognise the QR codes at the gate.

Staff-only and resort-locked: the resort comes from the signed-in account,
never from anything the client sends, and a file is only ever streamed after
that check (it is never a public /media/ URL).
"""
import mimetypes

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView

from users.models import User

from .leases import lease_meter_summary
from .models import Lease, LeaseAdult, LeaseDocument


class IsSecurity(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.SECURITY)


def _file_url(request, name, *args):
    return request.build_absolute_uri(reverse(name, args=args))


class StaffAdultSerializer(serializers.ModelSerializer):
    id_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = LeaseAdult
        fields = ("id", "full_name", "relation", "national_id", "id_photo_url")
        read_only_fields = fields

    def get_id_photo_url(self, obj):
        request = self.context.get("request")
        if not obj.id_photo or request is None:
            return None
        return _file_url(request, "staff_lease_adult_id", obj.lease_id, obj.id)


class StaffDocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = LeaseDocument
        fields = ("id", "kind", "label", "url")
        read_only_fields = fields

    def get_url(self, obj):
        request = self.context.get("request")
        if not obj.file or request is None:
            return None
        return _file_url(request, "staff_lease_document", obj.lease_id, obj.id)


class StaffLeaseSerializer(serializers.ModelSerializer):
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    status = serializers.SerializerMethodField()
    id_photo_url = serializers.SerializerMethodField()
    adults = StaffAdultSerializer(many=True, read_only=True)
    documents = StaffDocumentSerializer(many=True, read_only=True)
    meter_readings = serializers.SerializerMethodField()

    class Meta:
        model = Lease
        fields = (
            "id", "unit_key", "term", "status", "start_date", "end_date",
            "tenant_name", "tenant_phone", "tenant_national_id", "occupants", "id_photo_url",
            "adults", "documents", "meter_readings",
        )
        read_only_fields = fields

    def get_status(self, obj) -> str:
        return obj.status_on(timezone.localdate())

    def get_id_photo_url(self, obj):
        request = self.context.get("request")
        if not obj.tenant_id_photo or request is None:
            return None
        return _file_url(request, "staff_lease_tenant_id", obj.id)

    def get_meter_readings(self, obj):
        return lease_meter_summary(obj)


class StaffLeasePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class StaffLeaseListView(generics.ListAPIView):
    """
    The tenancies in the resort. By default the ones running or coming up;
    `?status=ENDED` for past ones, `?q=` to search by unit or tenant name.
    """
    permission_classes = [IsAuthenticated, IsSecurity]
    serializer_class = StaffLeaseSerializer
    pagination_class = StaffLeasePagination

    def get_queryset(self):
        resort = getattr(self.request, "tenant", None)
        if resort is None:
            return Lease.objects.none()
        today = timezone.localdate()
        qs = (
            Lease.objects.filter(resort=resort, cancelled_at__isnull=True)
            .select_related("unit")
            .prefetch_related("adults", "documents")
        )
        wanted = self.request.query_params.get("status", "CURRENT").upper()
        if wanted == "ACTIVE":
            qs = qs.filter(start_date__lte=today, end_date__gte=today)
        elif wanted == "UPCOMING":
            qs = qs.filter(start_date__gt=today)
        elif wanted == "ENDED":
            qs = qs.filter(end_date__lt=today)
        else:  # CURRENT: running or still to come
            qs = qs.filter(end_date__gte=today)
        query = self.request.query_params.get("q", "").strip()
        if query:
            from django.db.models import Q

            qs = qs.filter(Q(unit__unit_key__icontains=query) | Q(tenant_name__icontains=query))
        return qs.order_by("start_date", "id")

    @extend_schema(summary="Tenancies in my village (Security)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


def stream_file(field_file):
    """An authenticated download of a stored paper — never a public media URL."""
    content_type = mimetypes.guess_type(field_file.name)[0] or "application/octet-stream"
    return FileResponse(field_file.open("rb"), content_type=content_type)


class _StaffLeaseFileView(APIView):
    permission_classes = [IsAuthenticated, IsSecurity]

    def lease_in_my_resort(self, request, lease_pk):
        resort = getattr(request, "tenant", None)
        if resort is None:
            raise Http404
        return get_object_or_404(Lease, pk=lease_pk, resort=resort, cancelled_at__isnull=True)


class StaffLeaseTenantIdView(_StaffLeaseFileView):
    @extend_schema(summary="The tenant's ID photo (Security)", responses={200: bytes})
    def get(self, request, pk):
        lease = self.lease_in_my_resort(request, pk)
        if not lease.tenant_id_photo:
            raise Http404
        return stream_file(lease.tenant_id_photo)


class StaffLeaseAdultIdView(_StaffLeaseFileView):
    @extend_schema(summary="An adult's ID photo (Security)", responses={200: bytes})
    def get(self, request, pk, adult_id):
        lease = self.lease_in_my_resort(request, pk)
        adult = get_object_or_404(LeaseAdult, pk=adult_id, lease=lease)
        if not adult.id_photo:
            raise Http404
        return stream_file(adult.id_photo)


class StaffLeaseDocumentView(_StaffLeaseFileView):
    @extend_schema(summary="A paper sent with the rental (Security)", responses={200: bytes})
    def get(self, request, pk, document_id):
        lease = self.lease_in_my_resort(request, pk)
        document = get_object_or_404(LeaseDocument, pk=document_id, lease=lease)
        if not document.file:
            raise Http404
        return stream_file(document.file)
