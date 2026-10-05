from django.urls import path
from .views import (
    OwnerTicketListCreateView,
    PassApproveView,
    PassRejectView,
    PassRequestListView,
    PassScanListView,
    PassScanView,
    TicketAttachmentDownloadView,
    TicketDetailView,
    TicketMessageListCreateView,
    VisitorPassListCreateView,
)

app_name = "support"

urlpatterns = [
    path("api/owner/tickets/", OwnerTicketListCreateView.as_view(), name="ticket_list_create"),
    path("api/owner/tickets/<int:pk>/", TicketDetailView.as_view(), name="ticket_detail"),
    path("api/owner/tickets/<int:ticket_id>/messages/", TicketMessageListCreateView.as_view(), name="ticket_messages"),
    path("api/owner/messages/<int:pk>/attachment/", TicketAttachmentDownloadView.as_view(), name="ticket_attachment_download"),
    path("api/owner/passes/", VisitorPassListCreateView.as_view(), name="visitor_pass_list_create"),
    # Gate / beach-pool staff scanner app
    path("api/staff/passes/scan/", PassScanView.as_view(), name="pass_scan"),
    path("api/staff/passes/scans/", PassScanListView.as_view(), name="pass_scan_list"),
    path("api/staff/passes/requests/", PassRequestListView.as_view(), name="pass_request_list"),
    path("api/staff/passes/<int:pk>/approve/", PassApproveView.as_view(), name="pass_approve"),
    path("api/staff/passes/<int:pk>/reject/", PassRejectView.as_view(), name="pass_reject"),
]
