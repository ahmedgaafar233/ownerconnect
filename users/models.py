from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.conf import settings
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("phone is required")
        phone = phone.strip()
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.SUPERADMIN)
        return self.create_user(phone, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "Super Admin"
        RESORT_ADMIN = "RESORT_ADMIN", "Resort Admin"
        GENERAL_MANAGER = "GENERAL_MANAGER", "General Manager"
        FINANCIAL_MANAGER = "FINANCIAL_MANAGER", "Financial Manager"
        SUPERVISOR = "SUPERVISOR", "Supervisor"
        DATA_ENTRY = "DATA_ENTRY", "Data Entry"
        RECEPTION = "RECEPTION", "Reception"
        OWNER = "OWNER", "Owner"

    phone = models.CharField(max_length=20, unique=True)
    fullname = models.CharField(max_length=255, blank=True, null=True, verbose_name="Full Name")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if self.role == self.Role.SUPERADMIN:
            self.is_staff = True
            self.is_superuser = True

        if self.role in [
            self.Role.RESORT_ADMIN,
            self.Role.DATA_ENTRY,
            self.Role.SUPERVISOR,
            self.Role.FINANCIAL_MANAGER,
            self.Role.GENERAL_MANAGER,
            self.Role.RECEPTION,
        ]:
            self.is_staff = True
        elif self.role == self.Role.OWNER:
            self.is_staff = False

        super().save(*args, **kwargs)
        # Sync Group based on Role
        if self.role and self.role != self.Role.SUPERADMIN:
            from django.contrib.auth.models import Group
            group, _ = Group.objects.get_or_create(name=self.role)
            role_group_names = [
                self.Role.OWNER,
                self.Role.RECEPTION,
                self.Role.DATA_ENTRY,
                self.Role.SUPERVISOR,
                self.Role.FINANCIAL_MANAGER,
                self.Role.GENERAL_MANAGER,
            ]
            to_remove = list(
                self.groups.filter(name__in=role_group_names).exclude(name=self.role)
            )
            if to_remove:
                self.groups.remove(*to_remove)
            self.groups.add(group)
        elif self.role == self.Role.SUPERADMIN:
            pass

    resort = models.ForeignKey(
        "core.Resort",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "phone"
    objects = UserManager()

    def __str__(self):
        return self.phone

    @property
    def total_debt(self):
        """Calculate total debt for all units owned by this user"""
        from decimal import Decimal
        from django.db.models import Sum, Q
        from billing.models import Charge
        
        total = Charge.objects.filter(
            unit__owner_units__owner=self,
            status=Charge.Status.PUBLISHED
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        return total

    @property
    def total_paid(self):
        """Calculate total payments for all units owned by this user"""
        from decimal import Decimal
        from django.db.models import Sum
        from collections_app.models import Payment
        from billing.models import Charge
        
        total = Payment.objects.filter(
            charge__unit__owner_units__owner=self,
            charge__status=Charge.Status.PUBLISHED
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        return total

    @property
    def remaining_balance(self):
        """Calculate remaining balance for all units owned by this user"""
        return self.total_debt - self.total_paid

    @property
    def owned_units_info(self):
        """Get information about units owned by this user"""
        return [
            {
                'unit': owner_unit.unit,
                'unit_key': owner_unit.unit.unit_key,
                'building_no': owner_unit.unit.building_no,
                'unit_no': owner_unit.unit.unit_no,
            }
            for owner_unit in self.owner_units.select_related('unit').all()
        ]


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_teams",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Team"
        verbose_name_plural = "Teams"

    def __str__(self):
        return self.name


class TeamMembership(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="team_memberships_added",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Member"
        verbose_name_plural = "Members"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"],
                name="uniq_team_membership",
            )
        ]

    def __str__(self):
        return f"{self.team} - {self.user}"


class TeamMembershipRequest(models.Model):
    class Action(models.TextChoices):
        ADD = "ADD", "Add Member"
        REMOVE = "REMOVE", "Remove Member"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="requests")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_membership_requests",
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="team_membership_requests_created",
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="team_membership_requests_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Member Request"
        verbose_name_plural = "Member Requests"
        ordering = ("-requested_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user", "action", "status"],
                condition=models.Q(status="PENDING"),
                name="uniq_pending_team_request",
            )
        ]

    def __str__(self):
        return f"{self.team} - {self.user} - {self.action} ({self.status})"

    def approve(self, by_user):
        if self.status != self.Status.PENDING:
            return

        if self.action == self.Action.ADD:
            TeamMembership.objects.get_or_create(
                team=self.team,
                user=self.user,
                defaults={"added_by": by_user},
            )
        elif self.action == self.Action.REMOVE:
            TeamMembership.objects.filter(team=self.team, user=self.user).delete()

        self.status = self.Status.APPROVED
        self.decided_by = by_user
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "decided_by", "decided_at"])

    def reject(self, by_user, note=""):
        if self.status != self.Status.PENDING:
            return
        self.status = self.Status.REJECTED
        self.decided_by = by_user
        self.decided_at = timezone.now()
        if note is not None:
            self.decision_note = str(note)
            self.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
        else:
            self.save(update_fields=["status", "decided_by", "decided_at"])


class ActivationCode(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="activation_codes")
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.phone} - {self.code}"
class MobileDevice(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="devices")
    fcm_token = models.TextField()
    device_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    os = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.phone} - {self.os}"
