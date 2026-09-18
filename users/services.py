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
    def validate_activation_code(phone: str, code: str) -> User | None:
        """
        Validates the code for a given phone number.
        Returns the User if valid, None otherwise.
        """
        # Logic can be moved here from Serializer if we want strict separation
        pass
