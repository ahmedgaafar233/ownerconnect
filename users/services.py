import secrets
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from .models import User, ActivationCode

class UserService:
    @staticmethod
    def generate_activation_code(user: User) -> str:
        """
        Generates a 6-digit activation code for the given user.
        Expires in 24 hours.
        """
        code = f"{secrets.randbelow(1000000):06d}"
        
        # Ensure atomicity if we were doing more complex things, 
        # but here it's good practice anyway.
        with transaction.atomic():
            # Invalidate all previous unused codes before issuing a new one.
            # This ensures at most one valid code exists per user at any time,
            # minimising the brute-force attack surface.
            ActivationCode.objects.filter(user=user, used_at__isnull=True).delete()

            ActivationCode.objects.create(
                user=user,
                code=code,
                expires_at=timezone.now() + timedelta(hours=24),
            )
        return code

    @staticmethod
    def activate_user(activation: ActivationCode):
        """
        Marks an activation code as used.
        """
        activation.used_at = timezone.now()
        activation.save(update_fields=["used_at"])

    @staticmethod
    def validate_activation_code(phone: str, code: str) -> ActivationCode:
        """
        Validates the code for a given phone number. Shared by ActivateSerializer
        (admin-issued code, phone-only flow) and FirebaseAuthView's account-link
        branch (Google/Email-Password sign-in linking to a pre-provisioned owner).
        Raises ValueError with a user-facing message on failure.
        """
        phone = phone.strip()
        code = code.strip()

        try:
            user = User.objects.get(phone=phone, is_active=True)
        except User.DoesNotExist:
            raise ValueError("Invalid phone/code")

        activation = (
            ActivationCode.objects
            .filter(user=user, code=code, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not activation:
            raise ValueError("Invalid phone/code")

        if activation.expires_at and activation.expires_at < timezone.now():
            raise ValueError("Code expired")

        return activation
