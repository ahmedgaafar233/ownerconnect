from django.db import models
from django.conf import settings
from django.utils import timezone


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

    class ServiceType(models.TextChoices):
        """
        Stable code for what kind of service was asked for — the subject is
        free, localized text and can't be routed on. Who handles each type is
        data (ServiceRoute), not code, since it differs per resort.
        """
        ELECTRICIAN = "ELECTRICIAN", "Electrician"
        PLUMBER = "PLUMBER", "Plumber"
        CARPENTER = "CARPENTER", "Carpenter"
        SATELLITE = "SATELLITE", "Satellite Technician"
        GARDENING = "GARDENING", "Gardening & Agriculture"
        PEST_CONTROL = "PEST_CONTROL", "Pest Control"
        HOUSEKEEPING = "HOUSEKEEPING", "Housekeeping"

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
    service_type = models.CharField(max_length=20, choices=ServiceType.choices, blank=True, default="")
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    subject = models.CharField(max_length=255)
    # Optional: the app lets an owner just pick the kind of issue ("Electrician")
    # and add details only if they want to.
    description = models.TextField(blank=True, default="", help_text="Detailed description of the issue")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    
    # Who the desk sent to do the job — a staff account if the technician has
    # one, otherwise just their name.
    technician_name = models.CharField(max_length=120, blank=True, default="")

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


class VisitorPass(models.Model):
    class PassType(models.TextChoices):
        VISITOR = "VISITOR", "Visitor Access"
        TENANT = "TENANT", "Tenant Access"
        BEACH_ACCESS = "BEACH_ACCESS", "Beach Access"
        MAINTENANCE_WORKER = "MAINTENANCE_WORKER", "Maintenance Worker"

    class Status(models.TextChoices):
        # A resident's request waiting for Security (APPROVAL mode resorts).
        PENDING = "PENDING", "Pending approval"
        ACTIVE = "ACTIVE", "Active"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="visitor_passes")
    resort = models.ForeignKey("core.Resort", on_delete=models.CASCADE, related_name="visitor_passes")
    unit = models.ForeignKey("core.Unit", on_delete=models.CASCADE, related_name="visitor_passes")

    pass_type = models.CharField(max_length=20, choices=PassType.choices, default=PassType.VISITOR)
    visitor_name = models.CharField(max_length=255)
    national_id_or_passport = models.CharField(max_length=50, blank=True, default="")
    car_plate = models.CharField(max_length=50, blank=True, default="")
    
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    
    pass_code = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ACTIVE)
    # Set when the resort's own staff issued this pass for the resident
    # (`owner`) rather than the resident doing it from the app.
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="issued_passes"
    )
    # Who approved/rejected a pending request, when, and why (shown to the owner).
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_passes"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)

    # Only these draw down a unit's card allowance (Unit.card_allowance) —
    # guest and maintenance-worker passes are the owner's to issue freely.
    CARD_PASS_TYPES = (PassType.BEACH_ACCESS,)

    # What the beach/pool gate lets through: resident cards, and the access
    # pass a tenant's adults carry for the length of their rental (the same QR
    # that opens the village gate). The tenant pass is its own type so it does
    # not draw down the unit's card allowance.
    POOL_PASS_TYPES = (PassType.BEACH_ACCESS, PassType.TENANT)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def active_cards(cls, unit):
        """
        Cards still counting against the unit: live ones, and requests still
        waiting for Security — otherwise an owner could queue up requests
        past the allowance and have them all approved.
        """
        return cls.objects.filter(
            unit=unit,
            pass_type__in=cls.CARD_PASS_TYPES,
            status__in=(cls.Status.ACTIVE, cls.Status.PENDING),
            valid_to__gt=timezone.now(),
        )

    def save(self, *args, **kwargs):
        if not self.pass_code:
            import uuid
            self.pass_code = f"PASS-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.pass_type} - {self.visitor_name} ({self.pass_code})"



class PassScan(models.Model):
    """
    One scan of a pass QR by gate (Security) or beach/pool (Recreation) staff
    — an append-only audit log. Every scan is recorded, denials and unknown
    codes included, so management can see who tried to get in and why they
    were refused.
    """

    class Point(models.TextChoices):
        GATE = "GATE", "Security Gate"
        BEACH_POOL = "BEACH_POOL", "Beach / Pool"

    class Result(models.TextChoices):
        GRANTED = "GRANTED", "Granted"
        DENIED = "DENIED", "Denied"

    class DenyReason(models.TextChoices):
        NOT_FOUND = "NOT_FOUND", "Unknown pass"
        CANCELLED = "CANCELLED", "Pass cancelled"
        EXPIRED = "EXPIRED", "Pass expired"
        NOT_YET_VALID = "NOT_YET_VALID", "Pass not valid yet"
        WRONG_PASS_TYPE = "WRONG_PASS_TYPE", "Not a beach/pool card"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Not approved by Security yet"
        REJECTED = "REJECTED", "Request rejected"

    resort = models.ForeignKey("core.Resort", on_delete=models.CASCADE, related_name="pass_scans")
    # Null when the scanned code matched no pass in this resort; the raw code
    # is kept either way so such attempts can still be reviewed.
    visitor_pass = models.ForeignKey(
        VisitorPass, null=True, blank=True, on_delete=models.SET_NULL, related_name="scans"
    )
    pass_code = models.CharField(max_length=64)
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="pass_scans"
    )
    point = models.CharField(max_length=12, choices=Point.choices)
    result = models.CharField(max_length=10, choices=Result.choices)
    deny_reason = models.CharField(max_length=20, choices=DenyReason.choices, blank=True, default="")
    # Recreation only — towels handed out with this entry.
    towels_issued = models.PositiveSmallIntegerField(default=0)
    # Which phone / handheld / fixed scanner sent this, as the staff app
    # labels it ("Main gate 1") — lets management tell devices apart.
    device_label = models.CharField(max_length=60, blank=True, default="")
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scanned_at"]
        indexes = [
            models.Index(fields=["resort", "point", "scanned_at"]),
            models.Index(fields=["visitor_pass", "scanned_at"]),
        ]

    def __str__(self):
        return f"{self.point} {self.result} {self.pass_code}"

    @classmethod
    def deny_reason_for(cls, visitor_pass, point, now=None):
        """Why this pass must be refused at this point, or "" if it may enter."""
        now = now or timezone.now()
        if visitor_pass is None:
            return cls.DenyReason.NOT_FOUND
        if visitor_pass.status == VisitorPass.Status.PENDING:
            return cls.DenyReason.PENDING_APPROVAL
        if visitor_pass.status == VisitorPass.Status.REJECTED:
            return cls.DenyReason.REJECTED
        if visitor_pass.status == VisitorPass.Status.CANCELLED:
            return cls.DenyReason.CANCELLED
        if visitor_pass.status == VisitorPass.Status.EXPIRED or visitor_pass.valid_to < now:
            return cls.DenyReason.EXPIRED
        if visitor_pass.valid_from > now:
            return cls.DenyReason.NOT_YET_VALID
        # The gate admits every pass type; the beach/pool takes resident cards
        # and tenant access passes only.
        if point == cls.Point.BEACH_POOL and visitor_pass.pass_type not in VisitorPass.POOL_PASS_TYPES:
            return cls.DenyReason.WRONG_PASS_TYPE
        return ""
