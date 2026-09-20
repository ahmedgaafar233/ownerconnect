from django.urls import path
from .views import (
    OwnerTicketListCreateView,
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
]
