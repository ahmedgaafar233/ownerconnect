from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from users.models import User
from billing.models import Charge
from core.models import Unit, Resort
from support.models import Ticket

class Command(BaseCommand):
    help = 'Setup default roles and permissions for Delta Sharm Resort'

    def handle(self, *args, **options):
        roles = {
            User.Role.DATA_ENTRY: [
                "add_charge", "view_charge", "change_charge", # Can draft charges
                "view_unit",
                "add_excelupload", "view_excelupload",
            ],
            User.Role.SUPERVISOR: [
                "view_charge", "change_charge", # Can review
                "view_unit",
                "view_ticket", "change_ticket", # Can manage tickets
            ],
            User.Role.FINANCIAL_MANAGER: [
                "view_charge", "change_charge", "delete_charge", # Can publish/approve
                "view_payment", "add_payment", "change_payment",
                "view_unit",
            ],
            User.Role.GENERAL_MANAGER: [
                "view_charge", "view_payment",
                "view_unit", "view_resort",
                "view_ticket", "view_user",
                "view_excelupload"
            ],
            User.Role.RECEPTION: [
                "view_unit",
                "view_ticket", "change_ticket", "add_ticket",
                "view_user",
            ]
        }

        for role_name, codenames in roles.items():
            group, created = Group.objects.get_or_create(name=role_name)
            if created:
                self.stdout.write(f"Created group: {role_name}")
            else:
                self.stdout.write(f"Updated group: {role_name}")

            permissions = []
            for codename in codenames:
                try:
                    perm = Permission.objects.get(codename=codename)
                    permissions.append(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Permission not found: {codename}"))
            
            group.permissions.set(permissions)
            self.stdout.write(self.style.SUCCESS(f"Assigned {len(permissions)} permissions to {role_name}"))

        self.stdout.write(self.style.SUCCESS("Roles setup completed successfully."))
