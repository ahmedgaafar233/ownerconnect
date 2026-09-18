from django.http import Http404
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Ticket, Message, VisitorPass
from .serializers import (
    TicketSerializer,
    TicketCreateSerializer,
    MessageSerializer,
    VisitorPassSerializer,
)


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

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, "tenant", None)

        qs = Ticket.objects.select_related("unit", "resort", "owner", "assigned_to").prefetch_related("messages")

        if user.role == "OWNER":
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
        if user.role == "OWNER":
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
        if user.role == "OWNER":
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

        if user.role == "OWNER":
            if ticket.owner != user:
                raise Http404()
        elif not user.is_superuser:
            if not tenant or ticket.resort_id != tenant.id:
                raise Http404()

        msg = serializer.save(sender=self.request.user, ticket=ticket)

        # Notify ticket owner if reply is posted by staff/support
        if self.request.user != ticket.owner:
            try:
                from core.tasks import send_fcm_notification_task
                send_fcm_notification_task.delay(
                    user_id=ticket.owner_id,
                    title=f"Support Reply: {ticket.subject[:30]}",
                    body=msg.text[:100] if msg.text else "Staff replied to your support request.",
                    data={"type": "ticket_reply", "ticket_id": ticket.id},
                )
            except Exception as task_err:
                pass


class VisitorPassListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VisitorPassSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, "tenant", None)

        qs = VisitorPass.objects.select_related("unit", "resort", "owner")

        if user.role == "OWNER":
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
        serializer.save(
            owner=self.request.user,
            resort=unit.resort,
        )
