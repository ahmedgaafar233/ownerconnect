
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from core.models import Resort

User = get_user_model()

def setup_users():
    print("--- Setting up Test Users ---")
    
    # Ensure at least one resort exists
    resort = Resort.objects.first()
    if not resort:
        resort = Resort.objects.create(name="Delta Sharm Resort")
        print("Created default resort: Delta Sharm Resort")
    else:
        print(f"Using resort: {resort.name}")

    # Define roles and sample users
    users_to_create = [
        {"role": User.Role.SUPERADMIN, "phone": "01000000001", "name": "Admin User"},
        {"role": User.Role.GENERAL_MANAGER, "phone": "01000000002", "name": "General Manager"},
        {"role": User.Role.FINANCIAL_MANAGER, "phone": "01099998888", "name": "Financial Manager"}, # Already exists
        {"role": User.Role.SUPERVISOR, "phone": "01000000004", "name": "Supervisor User"},
        {"role": User.Role.DATA_ENTRY, "phone": "01000000005", "name": "Data Entry User"},
        {"role": User.Role.RECEPTION, "phone": "01000000006", "name": "Reception User"},
    ]

    password = "password123"

    for u_data in users_to_create:
        user, created = User.objects.get_or_create(
            phone=u_data["phone"],
            defaults={
                "role": u_data["role"],
                "resort": resort,
                "is_active": True
            }
        )
        
        # Ensure role and staff status are correct even if user existed
        user.role = u_data["role"]
        user.resort = resort
        user.set_password(password)
        user.save()
        
        status = "Created" if created else "Updated"
        print(f"{status}: {u_data['name']} ({u_data['role']}) - Login: {u_data['phone']} / {password}")

if __name__ == "__main__":
    setup_users()
