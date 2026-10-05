import logging

from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status, generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from core.models import Notification, Resort, Unit
from core.notifications import notify_user
from core.permissions import IsScannerStaff, IsSecurityStaff, ResidentsReadOnly
from core.tenancy import scope_to_tenant
from .models import Ticket, Message, PassScan, VisitorPass
from .passes import PassNotPending, approve_pass, notify_security_of_request, reject_pass
from .routing import limit_to_desk, route_new_ticket
from .serializers import (
    TicketSerializer,
    TicketCreateSerializer,
    MessageSerializer,
    PassRejectSerializer,
    PassRequestSerializer,
    PassScanRequestSerializer,
    PassScanSerializer,
    ScannedPassSerializer,
    VisitorPassSerializer,
)
from users.models import User

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 100


class OwnerTicketListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketCreateSerializer
        return TicketSerializer

    def create(self, request, *args, **kwargs):
        # TicketCreateSerializer only has the 5 writable input fields (no id,
        # status, mobile_ticket_id, created_at, ...) — the default
        # CreateModelMixin.create() would echo that same limited shape back
        # as the response, which crashed the mobile TicketModel.fromJson
        # (required `id` missing from the response). Re-serialize the
        # created instance with the full TicketSerializer instead.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = TicketSerializer(serializer.instance).data
        headers = self.get_success_headers(output)
        return Response(output, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, "tenant", None)

        qs = Ticket.objects.select_related("unit", "resort", "owner", "assigned_to").prefetch_related("messages")

        if user.role in (User.Role.OWNER, User.Role.TENANT):
            qs = qs.filter(owner=user)
        else:
            qs = limit_to_desk(user, scope_to_tenant(qs, self.request))

        # Filters
        category = self.request.query_params.get("category")
        status_param = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        service_type = self.request.query_params.get("service_type")
        # "I'll pay cash at the accounts office" notes are ACCOUNTS tickets,
        # but they belong to the payment flow, not the service-request list —
        # the app asks for everything except them.
        exclude_category = self.request.query_params.get("exclude_category")

        if exclude_category:
            qs = qs.exclude(category=exclude_category)
        if service_type:
            qs = qs.filter(service_type=service_type)
        # Staff inbox: "assigned=me" is the requests routed to the caller.
        if self.request.query_params.get("assigned") == "me":
            qs = qs.filter(assigned_to=user)
        if category:
            qs = qs.filter(category=category)
        if status_param:
            qs = qs.filter(status=status_param)
        if priority:
            qs = qs.filter(priority=priority)

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        unit = serializer.validated_data["unit"]

        # A Tenant only ever needs to raise maintenance requests — not
        # accounts/reception/etc issues that are the owner's concern.
        if (
            self.request.user.role == User.Role.TENANT
            and serializer.validated_data.get("category") != Ticket.Category.MAINTENANCE
        ):
            raise PermissionDenied("Tenants may only submit maintenance requests.")

        ticket = serializer.save(
            owner=self.request.user,
            resort=unit.resort,
        )
        try:
            route_new_ticket(ticket)
        except Exception as err:
            # The request is already saved — never fail the resident's
            # submission because telling the staff about it went wrong.
            logger.warning(f"Failed to route ticket {ticket.id}: {err}")


class TicketDetailView(generics.RetrieveUpdateDestroyAPIView):
    # Residents can read their ticket; status, assignee, resolution and the
    # unit it belongs to are staff-only to change, and a ticket staff have
    # already been told about isn't the resident's to delete.
    permission_classes = [IsAuthenticated, ResidentsReadOnly]
    serializer_class = TicketSerializer

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, "tenant", None)
        qs = Ticket.objects.select_related("unit", "resort", "owner", "assigned_to").prefetch_related("messages")

        # IDOR fix: this previously returned every ticket, from every resort,
        # to any authenticated non-owner (staff could retrieve/update/delete
        # another resort's ticket just by guessing its id). Staff are now
        # scoped to request.tenant (resolved by TenantMiddleware — a staff
        # member's own resort, never client-controlled); only a superuser
        # with no tenant resolved falls back to seeing everything.
        if user.role in (User.Role.OWNER, User.Role.TENANT):
            return qs.filter(owner=user)
        if tenant:
            return limit_to_desk(user, qs.filter(resort=tenant))
        if user.is_superuser:
            return qs
        return qs.none()


class TicketMessageListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        ticket_id = self.kwargs["ticket_id"]
        user = self.request.user
        tenant = getattr(self.request, "tenant", None)

        ticket = generics.get_object_or_404(Ticket, id=ticket_id)
        if user.role in (User.Role.OWNER, User.Role.TENANT):
            if ticket.owner != user:
                return Message.objects.none()
        elif not user.is_superuser:
            # Cross-tenant fix: a staff member could previously read another
            # resort's ticket messages just by knowing/guessing the ticket id,
            # since only the OWNER branch was ever checked here.
            if not tenant or ticket.resort_id != tenant.id:
                return Message.objects.none()

        return Message.objects.filter(ticket=ticket).select_related("sender").order_by("created_at")

    def perform_create(self, serializer):
        ticket_id = self.kwargs["ticket_id"]
        user = self.request.user
        tenant = getattr(self.request, "tenant", None)
        ticket = generics.get_object_or_404(Ticket, id=ticket_id)

        if user.role in (User.Role.OWNER, User.Role.TENANT):
            if ticket.owner != user:
                raise Http404()
        elif not user.is_superuser:
            if not tenant or ticket.resort_id != tenant.id:
                raise Http404()

        msg = serializer.save(sender=self.request.user, ticket=ticket)

        # Notify ticket owner if reply is posted by staff/support
        if self.request.user != ticket.owner:
            notify_user(
                ticket.owner,
                title=f"Support Reply: {ticket.subject[:30]}",
                body=msg.text[:100] if msg.text else "Staff replied to your support request.",
                notif_type=Notification.Type.TICKET_REPLY,
                data={"type": "ticket_reply", "ticket_id": ticket.id},
            )


class TicketAttachmentDownloadView(APIView):
    """
    Streams a support-ticket message's attachment after checking access —
    same reasoning as PaymentReceiptDownloadView: ticket_attachments/ used
    to be reachable straight off public /media/ serving with no login.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        tenant = getattr(request, "tenant", None)
        message = get_object_or_404(Message.objects.select_related("ticket"), pk=pk)
        ticket = message.ticket

        if user.role in (User.Role.OWNER, User.Role.TENANT):
            if ticket.owner_id != user.id:
                raise Http404
        elif not user.is_superuser:
            if not tenant or ticket.resort_id != tenant.id:
                raise Http404

        if not message.attachment:
            raise Http404

        return FileResponse(
            message.attachment.open("rb"),
            filename=message.attachment_name or message.attachment.name.rsplit("/", 1)[-1],
        )


class VisitorPassListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VisitorPassSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, "tenant", None)

        qs = VisitorPass.objects.select_related("unit", "resort", "owner")

        if user.role in (User.Role.OWNER, User.Role.TENANT):
            qs = qs.filter(owner=user)
        else:
            qs = scope_to_tenant(qs, self.request)

        pass_type = self.request.query_params.get("pass_type")
        status_param = self.request.query_params.get("status")

        if pass_type:
            qs = qs.filter(pass_type=pass_type)
        if status_param:
            qs = qs.filter(status=status_param)

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        unit = serializer.validated_data["unit"]

        # A Tenant only gets a pool/beach access pass, not visitor or
        # maintenance-worker passes — those are the owner's to issue.
        if (
            self.request.user.role == User.Role.TENANT
            and serializer.validated_data.get("pass_type") != VisitorPass.PassType.BEACH_ACCESS
        ):
            raise PermissionDenied("Tenants may only request a beach/pool access pass.")

        # Same cap for every role — the allowance belongs to the unit, so an
        # Owner and their Tenant draw from one shared pool. The unit row is
        # locked so two simultaneous requests can't both slip under the cap.
        with transaction.atomic():
            locked_unit = Unit.objects.select_for_update().select_related("unit_type").get(pk=unit.pk)
            allowance = locked_unit.card_allowance
            if (
                allowance is not None
                and serializer.validated_data.get("pass_type") in VisitorPass.CARD_PASS_TYPES
                and VisitorPass.active_cards(locked_unit).count() >= allowance
            ):
                raise ValidationError({
                    "unit": [
                        f"This unit's beach/pool card allowance ({allowance}) is fully used. "
                        "A card must expire or be cancelled before a new one can be issued."
                    ]
                })
            # Whether the pass works immediately or waits for Security is the
            # resort's own policy, not something the app chooses.
            needs_approval = unit.resort.pass_issuance_mode == Resort.PassIssuance.APPROVAL
            visitor_pass = serializer.save(
                owner=self.request.user,
                resort=unit.resort,
                status=VisitorPass.Status.PENDING if needs_approval else VisitorPass.Status.ACTIVE,
            )
        if needs_approval:
            try:
                notify_security_of_request(visitor_pass)
            except Exception as err:
                logger.warning(f"Failed to notify Security of pass request {visitor_pass.id}: {err}")


class PassScanView(APIView):
    """
    Security / Recreation staff scan a pass QR and get an on-the-spot
    verdict. Always answers 200 with result GRANTED or DENIED (a refused
    scan is a normal outcome, not an HTTP error) and records every attempt.

    Lookup is limited to the scanner's own resort — a code from another
    resort is indistinguishable from an unknown one — and the resort comes
    from the authenticated account, never from a client-supplied header.
    """
    permission_classes = [IsAuthenticated, IsScannerStaff]
    throttle_scope = "scan"

    def post(self, request):
        body = PassScanRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        code = body.validated_data["pass_code"]
        towels = body.validated_data["towels_issued"]

        resort = getattr(request, "tenant", None)
        if resort is None:
            raise PermissionDenied("This account is not assigned to a resort.")

        point = PassScan.Point.GATE if request.user.role == User.Role.SECURITY else PassScan.Point.BEACH_POOL
        if towels and point != PassScan.Point.BEACH_POOL:
            raise ValidationError({"towels_issued": ["Only Recreation staff issue towels."]})

        visitor_pass = (
            VisitorPass.objects.select_related("unit", "owner").filter(resort=resort, pass_code=code).first()
        )
        reason = PassScan.deny_reason_for(visitor_pass, point)
        granted = reason == ""

        scan = PassScan.objects.create(
            resort=resort,
            visitor_pass=visitor_pass,
            pass_code=code,
            scanned_by=request.user,
            point=point,
            result=PassScan.Result.GRANTED if granted else PassScan.Result.DENIED,
            deny_reason=reason,
            towels_issued=towels if granted else 0,
            device_label=body.validated_data["device_label"],
        )
        return Response({
            "scan_id": scan.id,
            "result": scan.result,
            "reason": scan.deny_reason,
            "pass": ScannedPassSerializer(visitor_pass, context={"point": point}).data if visitor_pass else None,
        })


class PassScanListView(generics.ListAPIView):
    """A scanner's own recent scans — what their app shows as history."""
    permission_classes = [IsAuthenticated, IsScannerStaff]
    serializer_class = PassScanSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return PassScan.objects.none()
        return (
            PassScan.objects.filter(resort=tenant, scanned_by=self.request.user)
            .select_related("visitor_pass__unit")
        )


class PassRequestListView(generics.ListAPIView):
    """
    Security's queue of pass requests in their own resort. Defaults to what
    still needs a decision, oldest first; ?status= looks at the rest.
    """
    permission_classes = [IsAuthenticated, IsSecurityStaff]
    serializer_class = PassRequestSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return VisitorPass.objects.none()
        status_param = self.request.query_params.get("status", VisitorPass.Status.PENDING)
        return (
            VisitorPass.objects.filter(resort=tenant, status=status_param)
            .select_related("unit__unit_type", "owner")
            .order_by("created_at")
        )


class _PassDecisionView(APIView):
    permission_classes = [IsAuthenticated, IsSecurityStaff]

    def _pending_pass(self, request, pk):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            raise Http404
        return get_object_or_404(VisitorPass.objects.select_related("unit", "owner"), pk=pk, resort=tenant)

    def _respond(self, decide):
        try:
            decided = decide()
        except PassNotPending:
            return Response({"detail": "This request has already been decided."}, status=status.HTTP_409_CONFLICT)
        return Response(PassRequestSerializer(decided).data)


class PassApproveView(_PassDecisionView):
    def post(self, request, pk):
        visitor_pass = self._pending_pass(request, pk)
        return self._respond(lambda: approve_pass(visitor_pass, request.user))


class PassRejectView(_PassDecisionView):
    def post(self, request, pk):
        body = PassRejectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        visitor_pass = self._pending_pass(request, pk)
        return self._respond(lambda: reject_pass(visitor_pass, request.user, body.validated_data["reason"]))
