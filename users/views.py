import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from .models import User, ActivationCode
from .serializers import ActivateSerializer, MeSerializer, GenerateCodeSerializer
from .services import UserService

logger = logging.getLogger("users")

class ActivateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Activate User Account",
        description="Validates the activation code and returns JWT tokens.",
        request=ActivateSerializer,
        responses={200: "JWT Token Pair"},
    )
    def post(self, request):
        ser = ActivateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user = ser.validated_data["user"]
        activation = ser.validated_data["activation"]

        # Delegate activation logic to service
        UserService.activate_user(activation)

        refresh = RefreshToken.for_user(user)
        
        logger.info(f"User {user.phone} activated successfully.")
        
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": MeSerializer(user).data,
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get Current User Profile",
        responses={200: MeSerializer},
    )
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class GenerateActivationCodeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Generate Activation Code (Admin)",
        description="Generates a new activation code for an existing user. Requires SUPERADMIN or RESORT_ADMIN role.",
        request=GenerateCodeSerializer,
        responses={200: OpenApiExample("Response", value={"phone": "+123456789", "code": "123456"})},
    )
    def post(self, request):
        # NOTE: Role check could be moved to a Permission Class for better reusability
        if request.user.role not in [User.Role.SUPERADMIN, User.Role.RESORT_ADMIN]: # type: ignore
             logger.warning(f"User {request.user.phone} attempted to generate code without permission.")
             return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        ser = GenerateCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        phone = ser.validated_data["phone"]

        try:
            target = User.objects.get(phone=phone)
        except User.DoesNotExist:
             return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Resort admin validation
        if request.user.role == User.Role.RESORT_ADMIN: # type: ignore
            if not request.user.resort_id or target.resort_id != request.user.resort_id: # type: ignore
                logger.warning(f"Resort Admin {request.user.phone} attempted to access user {phone} from different resort.")
                return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        code = UserService.generate_activation_code(target)
        
        logger.info(f"Activation code generated for {phone} by {request.user.phone}")
        
        return Response({"phone": phone, "code": code})