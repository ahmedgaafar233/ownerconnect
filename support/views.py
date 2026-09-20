from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status, generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from core.models import Notification
from core.notifications import notify_user
from .models import Ticket, Message, VisitorPass
from .serializers import (
    TicketSerializer,
    TicketCreateSerializer,
    MessageSerializer,
    VisitorPassSerializer,
)
from users.models import User


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
        elif tenant:
            qs = qs.filter(resort=tenant)

        # Filters
        category = self.request.query_params.get("category")
        status_param = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")

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

        serializer.save(
            owner=self.request.user,
            resort=unit.resort,
        )


class TicketDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
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
            return qs.filter(resort=tenant)
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
        elif tenant:
            qs = qs.filter(resort=tenant)

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

        serializer.save(
            owner=self.request.user,
            resort=unit.resort,
        )
