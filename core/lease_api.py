from typing import Optional

from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User

from .leases import (
    LeaseError,
    add_adult,
    add_document,
    end_lease,
    extend_lease,
    lease_meter_summary,
    max_adults,
    register_lease,
    remove_adult,
    remove_document,
    renew_lease,
)
from .models import Lease, LeaseAdult, LeaseDocument, Unit

MAX_ID_PHOTO_BYTES = 8 * 1024 * 1024


def _pass_data(visitor_pass):
    """The part of a QR pass the app needs: the code to draw, and whether it works."""
    if visitor_pass is None:
        return None
    return {
        "id": visitor_pass.id,
        "pass_code": visitor_pass.pass_code,
        "status": visitor_pass.status,
        "valid_from": visitor_pass.valid_from,
        "valid_to": visitor_pass.valid_to,
    }


class LeaseAdultSerializer(serializers.ModelSerializer):
    has_id_photo = serializers.SerializerMethodField()
    access = serializers.SerializerMethodField()

    class Meta:
        model = LeaseAdult
        fields = ("id", "full_name", "national_id", "relation", "has_id_photo", "access")
        read_only_fields = fields

    def get_has_id_photo(self, obj) -> bool:
        return bool(obj.id_photo)

    def get_access(self, obj):
        return _pass_data(obj.access_pass)


class LeaseDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaseDocument
        fields = ("id", "kind", "label")
        read_only_fields = fields


class LeaseSerializer(serializers.ModelSerializer):
    """What the owner sees about a rental of theirs."""
    unit_key = serializers.CharField(source="unit.unit_key", read_only=True)
    status = serializers.SerializerMethodField()
    has_id_photo = serializers.SerializerMethodField()
    tenant_balance = serializers.SerializerMethodField()
    tenant_cleared = serializers.SerializerMethodField()
    access = serializers.SerializerMethodField()
    adults = LeaseAdultSerializer(many=True, read_only=True)
    documents = LeaseDocumentSerializer(many=True, read_only=True)
    max_adults = serializers.SerializerMethodField()
    meter_readings = serializers.SerializerMethodField()

    class Meta:
        model = Lease
        fields = (
            "id", "unit", "unit_key", "term", "status", "start_date", "end_date",
            "tenant_name", "tenant_phone", "tenant_national_id", "occupants", "has_id_photo",
            "tenant_balance", "tenant_cleared", "access", "adults", "documents", "max_adults",
            "meter_readings", "created_at",
        )
        read_only_fields = fields

    def get_access(self, obj):
        """The tenant's own gate-and-pool QR (each further adult's is in `adults`)."""
        return _pass_data(obj.access_pass)

    def get_max_adults(self, obj) -> int:
        return max_adults(obj.unit)

    def get_meter_readings(self, obj):
        """Maintenance's entry/exit readings of the unit's meters for this rental."""
        return lease_meter_summary(obj)

    def get_status(self, obj) -> str:
        return obj.status_on(timezone.localdate())

    def get_has_id_photo(self, obj) -> bool:
        return bool(obj.tenant_id_photo)

    def _balance(self, obj):
        # Only a long lease has a tenant account whose payments matter. The
        # owner needs this to know when it is safe to hand the deposit back.
        if obj.term != Lease.Term.LONG or obj.cancelled_at:
            return None
        from billing.lease_rules import tenant_balance
        return tenant_balance(obj)

    def get_tenant_balance(self, obj) -> Optional[str]:
        balance = self._balance(obj)
        return None if balance is None else str(balance)

    def get_tenant_cleared(self, obj) -> Optional[bool]:
        balance = self._balance(obj)
        return None if balance is None else balance <= 0


class LeaseCreateSerializer(serializers.Serializer):
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all())
    term = serializers.ChoiceField(choices=Lease.Term.choices)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    tenant_name = serializers.CharField(max_length=255)
    tenant_phone = serializers.CharField(max_length=30)
    tenant_national_id = serializers.CharField(max_length=50)
    tenant_id_photo = serializers.ImageField()
    occupants = serializers.IntegerField(min_value=1, max_value=30)

    def validate_tenant_id_photo(self, value):
        if value.size > MAX_ID_PHOTO_BYTES:
            raise serializers.ValidationError("The photo is too large (8 MB at most).")
        return value


class AdultCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    national_id = serializers.CharField(max_length=50)
    id_photo = serializers.ImageField()
    relation = serializers.ChoiceField(choices=LeaseAdult.Relation.choices, default=LeaseAdult.Relation.SPOUSE)

    def validate_id_photo(self, value):
        if value.size > MAX_ID_PHOTO_BYTES:
            raise serializers.ValidationError("The photo is too large (8 MB at most).")
        return value


class DocumentCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=LeaseDocument.Kind.choices)
    label = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    file = serializers.ImageField()

    def validate_file(self, value):
        if value.size > MAX_ID_PHOTO_BYTES:
            raise serializers.ValidationError("The photo is too large (8 MB at most).")
        return value


class ExtendSerializer(serializers.Serializer):
    end_date = serializers.DateField()


class RenewSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    term = serializers.ChoiceField(choices=Lease.Term.choices, required=False)


def _require_owner(user):
    if user.role != User.Role.OWNER:
        raise PermissionDenied("Only owners can rent units out.")


class LeaseListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "lease"

    @extend_schema(summary="My rentals (Owner)", responses={200: LeaseSerializer(many=True)})
    def get(self, request):
        _require_owner(request.user)
        leases = Lease.objects.filter(landlord=request.user).select_related("unit")
        unit = request.query_params.get("unit")
        if unit and unit.isdigit():
            leases = leases.filter(unit_id=int(unit))
        return Response(LeaseSerializer(leases, many=True, context={"request": request}).data)

    @extend_schema(
        summary="Rent a unit out (Owner)",
        description=(
            "Registers the tenant and the period. Needs no approval — the village's Reception and Security are "
            "notified. A LONG lease creates the tenant's account and moves the unit's water/electricity for the "
            "lease months to it; a SHORT stay is only a record. Multipart, because of the ID photo."
        ),
        request={"multipart/form-data": LeaseCreateSerializer},
        responses={201: LeaseSerializer},
    )
    def post(self, request):
        _require_owner(request.user)
        serializer = LeaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            lease = register_lease(
                landlord=request.user,
                unit=data["unit"],
                term=data["term"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                tenant_name=data["tenant_name"],
                tenant_phone=data["tenant_phone"],
                tenant_national_id=data["tenant_national_id"],
                tenant_id_photo=data["tenant_id_photo"],
                occupants=data["occupants"],
            )
        except LeaseError as exc:
            return Response({exc.field: [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(LeaseSerializer(lease, context={"request": request}).data, status=status.HTTP_201_CREATED)


def _my_lease(request, pk):
    """One of the caller's own rentals — someone else's id is a plain 404."""
    _require_owner(request.user)
    return get_object_or_404(
        Lease.objects.select_related("unit", "tenant", "access_pass"), pk=pk, landlord=request.user
    )


def _lease_response(request, lease, code=status.HTTP_200_OK):
    lease.refresh_from_db()
    return Response(LeaseSerializer(lease, context={"request": request}).data, status=code)


def _refused(exc, code=status.HTTP_400_BAD_REQUEST):
    return Response({exc.field: [str(exc)]}, status=code)


class LeaseAdultCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "lease"

    @extend_schema(
        summary="Register another adult staying in a rented unit (Owner)",
        request={"multipart/form-data": AdultCreateSerializer},
        responses={201: LeaseSerializer},
    )
    def post(self, request, pk):
        lease = _my_lease(request, pk)
        body = AdultCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            add_adult(lease, **body.validated_data)
        except LeaseError as exc:
            return _refused(exc)
        return _lease_response(request, lease, status.HTTP_201_CREATED)


class LeaseAdultDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Remove an adult from a rental (Owner)", responses={200: LeaseSerializer})
    def delete(self, request, pk, adult_id):
        lease = _my_lease(request, pk)
        remove_adult(get_object_or_404(LeaseAdult, pk=adult_id, lease=lease))
        return _lease_response(request, lease)


class LeaseDocumentCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "lease"

    @extend_schema(
        summary="Add a paper (marriage certificate, passport…) to a rental (Owner)",
        request={"multipart/form-data": DocumentCreateSerializer},
        responses={201: LeaseSerializer},
    )
    def post(self, request, pk):
        lease = _my_lease(request, pk)
        body = DocumentCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            add_document(lease, **body.validated_data)
        except LeaseError as exc:
            return _refused(exc)
        return _lease_response(request, lease, status.HTTP_201_CREATED)


class LeaseDocumentDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Remove a paper from a rental (Owner)", responses={200: LeaseSerializer})
    def delete(self, request, pk, document_id):
        lease = _my_lease(request, pk)
        remove_document(get_object_or_404(LeaseDocument, pk=document_id, lease=lease))
        return _lease_response(request, lease)


class LeaseExtendView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Extend a running rental (Owner)",
        description="Moves the end date later. The tenant's and every adult's QR keep working through the extra time.",
        request=ExtendSerializer,
        responses={200: LeaseSerializer},
    )
    def post(self, request, pk):
        lease = _my_lease(request, pk)
        body = ExtendSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            extend_lease(lease, body.validated_data["end_date"])
        except LeaseError as exc:
            return _refused(exc)
        return _lease_response(request, lease)


class LeaseRenewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Start a new rental period for the same tenant (Owner)",
        description="Same people, same papers and the same QR passes, now valid for the new period.",
        request=RenewSerializer,
        responses={201: LeaseSerializer},
    )
    def post(self, request, pk):
        lease = _my_lease(request, pk)
        body = RenewSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            new = renew_lease(lease, **body.validated_data)
        except LeaseError as exc:
            return _refused(exc)
        return _lease_response(request, new, status.HTTP_201_CREATED)


class LeaseEndView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="End or cancel one of my rentals (Owner)", request=None, responses={200: LeaseSerializer})
    def post(self, request, pk):
        _require_owner(request.user)
        # Scoped to the caller's own leases: someone else's id is a plain 404.
        lease = get_object_or_404(Lease.objects.select_related("unit", "tenant"), pk=pk, landlord=request.user)
        try:
            end_lease(lease)
        except LeaseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(LeaseSerializer(lease, context={"request": request}).data)


_ID_PHOTO_ROLES = (
    User.Role.SUPERADMIN,
    User.Role.RESORT_ADMIN,
    User.Role.GENERAL_MANAGER,
    User.Role.SUPERVISOR,
    User.Role.RECEPTION,
)


def _admin_may_open(user, lease):
    return user.is_superuser or (user.role in _ID_PHOTO_ROLES and user.resort_id == lease.resort_id)


@staff_member_required
def lease_id_photo_view(request, pk):
    """
    The tenant's ID photo, for the village's own front-of-house staff only —
    never a public /media/ file (an ID document is exactly what must not be
    guessable by id). Anyone else, or another village's staff, gets a 404.
    """
    lease = get_object_or_404(Lease, pk=pk)
    if not _admin_may_open(request.user, lease) or not lease.tenant_id_photo:
        raise Http404
    return FileResponse(lease.tenant_id_photo.open("rb"))


@staff_member_required
def lease_adult_id_view(request, pk):
    """An adult's ID photo — same rule as the tenant's."""
    adult = get_object_or_404(LeaseAdult.objects.select_related("lease"), pk=pk)
    if not _admin_may_open(request.user, adult.lease) or not adult.id_photo:
        raise Http404
    return FileResponse(adult.id_photo.open("rb"))


@staff_member_required
def lease_document_view(request, pk):
    """A paper sent with a rental (marriage certificate, passport…) — same rule."""
    document = get_object_or_404(LeaseDocument.objects.select_related("lease"), pk=pk)
    if not _admin_may_open(request.user, document.lease) or not document.file:
        raise Http404
    return FileResponse(document.file.open("rb"))
