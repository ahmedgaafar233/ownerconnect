from django.db import models
from django.conf import settings


class Ticket(models.Model):
    class Category(models.TextChoices):
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        CLEANING = "CLEANING", "Cleaning"
        ACCOUNTS = "ACCOUNTS", "Accounts"
        HOUSEKEEPING = "HOUSEKEEPING", "Housekeeping"
        RECEPTION = "RECEPTION", "Reception"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        PENDING_OWNER = "PENDING_OWNER", "Pending Owner"
        COMPLETED = "COMPLETED", "Completed"
        CLOSED = "CLOSED", "Closed"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets"
    )
    resort = models.ForeignKey(
        "core.Resort",
        on_delete=models.CASCADE,
        related_name="tickets"
    )
    unit = models.ForeignKey(
        "core.Unit",
        on_delete=models.CASCADE,
        related_name="tickets"
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    subject = models.CharField(max_length=255)
    description = models.TextField(help_text="Detailed description of the issue")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    
    # For maintenance/cleaning assignments
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        help_text="Staff member assigned to this ticket"
    )
    
    # Resolution tracking
    resolution_notes = models.TextField(blank=True, default="", help_text="Notes about how the issue was resolved")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_tickets"
    )
    
    # For Flutter app integration
    mobile_ticket_id = models.CharField(max_length=50, blank=True, default="", unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["category", "status"]),
            models.Index(fields=["assigned_to", "status"]),
        ]

    def __str__(self):
        return f"{self.category} - {self.subject} ({self.owner.phone})"

    def save(self, *args, **kwargs):
        # Generate mobile ticket ID if not set
        if not self.mobile_ticket_id:
            import uuid
            self.mobile_ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        
        # Set resolved timestamp when status changes to completed
        if self.status == self.Status.COMPLETED and not self.resolved_at:
            from django.utils import timezone
            self.resolved_at = timezone.now()
        
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Check if ticket is overdue based on priority"""
        from django.utils import timezone
        import datetime
        
        if self.status in [self.Status.COMPLETED, self.Status.CLOSED]:
            return False
        
        now = timezone.now()
        if self.priority == self.Priority.URGENT:
            deadline = self.created_at + datetime.timedelta(hours=4)
        elif self.priority == self.Priority.HIGH:
            deadline = self.created_at + datetime.timedelta(hours=24)
        elif self.priority == self.Priority.MEDIUM:
            deadline = self.created_at + datetime.timedelta(days=3)
        else:  # LOW
            deadline = self.created_at + datetime.timedelta(days=7)
        
        return now > deadline


class Message(models.Model):
    class MessageType(models.TextChoices):
        TEXT = "TEXT", "Text"
        IMAGE = "IMAGE", "Image"
        FILE = "FILE", "File"
        SYSTEM = "SYSTEM", "System"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=10, choices=MessageType.choices, default=MessageType.TEXT)
    content = models.TextField()
    
    # For file attachments
    attachment = models.FileField(
        upload_to="ticket_attachments/",
        null=True,
        blank=True,
        help_text="Attach images or files related to the ticket"
    )
    attachment_name = models.CharField(max_length=255, blank=True, default="")
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
            models.Index(fields=["sender", "is_read"]),
        ]

    def __str__(self):
        return f"Msg from {self.sender.phone} on ticket {self.ticket.id}"

    def save(self, *args, **kwargs):
        # Set attachment name if not provided
        if self.attachment and not self.attachment_name:
            self.attachment_name = self.attachment.name
        
        # Auto-generate system messages for status changes
        if not self.pk and self.message_type == self.MessageType.SYSTEM:
            pass  # System messages are created automatically
        
        super().save(*args, **kwargs)
