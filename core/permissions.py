from django.contrib import admin
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission
from users.models import User


class ResidentsReadOnly(BasePermission):
    """Owners and Tenants may look at a record but never change or delete it."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.role not in (User.Role.OWNER, User.Role.TENANT)


class IsSecurityStaff(BasePermission):
    """Security only — the staff who confirm pass requests."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.SECURITY)


class IsScannerStaff(BasePermission):
    """Gate (Security) and beach/pool (Recreation) scanner accounts only."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and user.role in (User.Role.SECURITY, User.Role.RECREATION)
        )


class RoleBasedAdminMixin:
    """
    Mixin to restrict admin access based on user roles
    """
    required_roles = []  # Override in subclasses
    
    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if self.required_roles:
            return request.user.role in self.required_roles
        return super().has_view_permission(request, obj)
    
    def has_add_permission(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if self.required_roles:
            return request.user.role in self.required_roles
        return super().has_add_permission(request)
    
    def has_change_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if self.required_roles:
            return request.user.role in self.required_roles
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if self.required_roles:
            return request.user.role in self.required_roles
        return super().has_delete_permission(request, obj)
    
    def has_module_permission(self, request):
        if not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if self.required_roles:
            return request.user.role in self.required_roles
        return super().has_module_permission(request)


class DataEntryAdminMixin(RoleBasedAdminMixin):
    """For Data Entry role - basic operational views"""
    required_roles = [User.Role.DATA_ENTRY, User.Role.SUPERVISOR, User.Role.FINANCIAL_MANAGER, User.Role.GENERAL_MANAGER]


class ImportUploadMixin(RoleBasedAdminMixin):
    """For uploading Excel/CSV files - restricted to Supervisors and Managers"""
    required_roles = [User.Role.SUPERVISOR, User.Role.FINANCIAL_MANAGER, User.Role.GENERAL_MANAGER]


class ImportProcessMixin(RoleBasedAdminMixin):
    """For processing uploaded files - restricted to Managers only"""
    required_roles = [User.Role.FINANCIAL_MANAGER, User.Role.GENERAL_MANAGER]


class SupervisorAdminMixin(RoleBasedAdminMixin):
    """For Supervisor role - can review and mark charges as reviewed"""
    required_roles = [User.Role.SUPERVISOR, User.Role.FINANCIAL_MANAGER, User.Role.GENERAL_MANAGER]


class FinancialManagerAdminMixin(RoleBasedAdminMixin):
    """For Financial Manager role - can approve and publish charges"""
    required_roles = [User.Role.FINANCIAL_MANAGER, User.Role.GENERAL_MANAGER]


class GeneralManagerAdminMixin(RoleBasedAdminMixin):
    """For General Manager role - full access to financial operations"""
    required_roles = [User.Role.GENERAL_MANAGER]


class ReceptionAdminMixin(RoleBasedAdminMixin):
    """For Reception role - can view support tickets and basic info"""
    required_roles = [User.Role.RECEPTION, User.Role.SUPERVISOR, User.Role.FINANCIAL_MANAGER, User.Role.GENERAL_MANAGER]


class OwnerAdminMixin(RoleBasedAdminMixin):
    """For Owner role - can only view their own data"""
    required_roles = [User.Role.OWNER]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.role == User.Role.OWNER:
            # Filter to show only owner's data
            return qs.filter(owner=request.user)
        return qs
