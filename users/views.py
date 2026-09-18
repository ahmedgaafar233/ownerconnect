import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from django.conf import settings

from .models import User, ActivationCode, MobileDevice
from .serializers import (
    ActivateSerializer,
    MeSerializer,
    GenerateCodeSerializer,
    FirebaseAuthSerializer,
    FCMTokenRegisterSerializer,
)
from .services import UserService

logger = logging.getLogger("users")


class FirebaseAuthView(APIView):
    """
    Receives Firebase ID Token obtained from Firebase Phone Auth on the mobile app.
    Verifies the token via firebase_admin SDK, gets/creates the matching User by phone,
    and returns SimpleJWT Access & Refresh tokens.
    """
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(
        summary="Firebase Phone Auth Exchange",
        description="Exchanges a Firebase ID Token for system SimpleJWT tokens.",
        request=FirebaseAuthSerializer,
        responses={200: "JWT Token Pair"},
    )
    def post(self, request):
        serializer = FirebaseAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        id_token = serializer.validated_data["id_token"]

        phone_number = None

        try:
            import firebase_admin
            from firebase_admin import auth as fb_auth

            if not firebase_admin._apps:
                cred_file = getattr(settings, "FIREBASE_CREDENTIALS_FILE", None)
                if cred_file:
                    cred = firebase_admin.credentials.Certificate(cred_file)
                    firebase_admin.initialize_app(cred)
                else:
                    firebase_admin.initialize_app()

            decoded_token = fb_auth.verify_id_token(id_token)
            phone_number = decoded_token.get("phone_number")
        except Exception as e:
            logger.warning(f"Firebase token verification failed: {e}")
            # Was gated on settings.DEBUG alone: any environment accidentally
            # left with DEBUG=True let a client authenticate as ANY phone
            # number just by sending "dev_test_token_<phone>". Now gated on
            # the dedicated ALLOW_DEV_AUTH_BYPASS switch (see settings.py),
            # which defaults to False independently of DEBUG.
            if getattr(settings, "ALLOW_DEV_AUTH_BYPASS", False) and id_token.startswith("dev_test_token_"):
                phone_number = id_token.replace("dev_test_token_", "")
            else:
                return Response(
                    {"detail": "Invalid or expired Firebase ID token."},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        if not phone_number:
            return Response(
                {"detail": "Firebase token does not contain a verified phone number."},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone_number = phone_number.strip()

        user, created = User.objects.get_or_create(
            phone=phone_number,
            defaults={
                "role": User.Role.OWNER,
                "is_active": True,
            }
        )

        if not user.is_active:
            return Response(
                {"detail": "User account is disabled."},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)
        logger.info(f"User {user.phone} authenticated via Firebase (created={created}).")

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": MeSerializer(user).data,
        }, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)


class FCMTokenRegisterView(APIView):
    """
    Registers or updates an FCM device token for push notifications for the current authenticated user.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Register FCM Device Token",
        description="Registers or updates the user's mobile device FCM token for push notifications.",
        request=FCMTokenRegisterSerializer,
        responses={200: OpenApiExample("Success", value={"status": "registered"})},
    )
    def post(self, request):
        serializer = FCMTokenRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fcm_token = serializer.validated_data["fcm_token"]
        device_id = serializer.validated_data.get("device_id") or None
        os = serializer.validated_data.get("os") or ""

        if device_id:
            device, created = MobileDevice.objects.update_or_create(
                device_id=device_id,
                defaults={
                    "user": request.user,
                    "fcm_token": fcm_token,
                    "os": os,
                }
            )
        else:
            device, created = MobileDevice.objects.update_or_create(
                user=request.user,
                fcm_token=fcm_token,
                defaults={
                    "os": os,
                }
            )

        logger.info(f"FCM token registered for user {request.user.phone} (device_id={device_id}, created={created})")
        return Response({"status": "registered", "device_id": device.device_id}, status=status.HTTP_200_OK)


class ActivateView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

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
    throttle_scope = "auth"

    @extend_schema(
        summary="Generate Activation Code (Admin)",
        description="Generates a new activation code for an existing user. Requires SUPERADMIN or RESORT_ADMIN role.",
        request=GenerateCodeSerializer,
        responses={200: OpenApiExample("Response", value={"phone": "+123456789", "code": "123456"})},
    )
    def post(self, request):
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

        if request.user.role == User.Role.RESORT_ADMIN: # type: ignore
            if not request.user.resort_id or target.resort_id != request.user.resort_id: # type: ignore
                logger.warning(f"Resort Admin {request.user.phone} attempted to access user {phone} from different resort.")
                return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        code = UserService.generate_activation_code(target)
        
        logger.info(f"Activation code generated for {phone} by {request.user.phone}")
        
        return Response({"phone": phone, "code": code})