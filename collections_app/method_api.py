"""
Saved ways to pay: mobile wallet, InstaPay, Fawry. Everything here is scoped to
the signed-in person — nobody can list, change or remove anyone else's — and
no card number is ever accepted: bank cards are added through the payment
gateway's own secure form once online payments are live, so the API only
reports that cards aren't available yet.
"""
import re

from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from users.models import User

from .models import PaymentMethod

MAX_METHODS = 10
_PHONE_RE = re.compile(r"^\+\d{8,15}$")
# name@bank — the InstaPay address (IPA) format: letters, digits, dot, dash, underscore, then @provider.
_INSTAPAY_RE = re.compile(r"^[A-Za-z0-9._-]{3,40}@[A-Za-z0-9]{2,25}$")
# A value someone typed in to mark where the real key goes isn't a linked gateway.
_PLACEHOLDER_RE = re.compile(r"(replace|placeholder|changeme|your[-_ ]|example|xxx)", re.IGNORECASE)


def gateway_is_linked():
    """Whether the village's Paymob account is really configured (not empty, not a placeholder)."""
    values = (settings.PAYMOB_API_KEY, settings.PAYMOB_IFRAME_ID)
    return all(v and not _PLACEHOLDER_RE.search(v) for v in values)


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ("id", "kind", "label", "wallet_provider", "wallet_phone", "instapay_address", "is_default", "created_at")
        read_only_fields = fields


class PaymentMethodCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=[PaymentMethod.Kind.WALLET, PaymentMethod.Kind.INSTAPAY, PaymentMethod.Kind.FAWRY])
    wallet_provider = serializers.ChoiceField(choices=PaymentMethod.Wallet.choices, required=False)
    wallet_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    instapay_address = serializers.CharField(max_length=80, required=False, allow_blank=True)
    make_default = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        kind = attrs["kind"]
        if kind == PaymentMethod.Kind.WALLET:
            phone = re.sub(r"[\s\-()]", "", attrs.get("wallet_phone", ""))
            if not _PHONE_RE.match(phone):
                raise serializers.ValidationError({"wallet_phone": ["Enter the wallet's phone number with its country code."]})
            if not attrs.get("wallet_provider"):
                raise serializers.ValidationError({"wallet_provider": ["Choose the wallet."]})
            attrs["wallet_phone"] = phone
        elif kind == PaymentMethod.Kind.INSTAPAY:
            address = (attrs.get("instapay_address") or "").strip()
            if not _INSTAPAY_RE.match(address):
                raise serializers.ValidationError({"instapay_address": ["Enter a valid InstaPay address, like name@instapay."]})
            attrs["instapay_address"] = address
        return attrs


def _label_for(kind, data):
    if kind == PaymentMethod.Kind.WALLET:
        provider = dict(PaymentMethod.Wallet.choices)[data["wallet_provider"]]
        return f"{provider} · {data['wallet_phone']}"
    if kind == PaymentMethod.Kind.INSTAPAY:
        return f"InstaPay · {data['instapay_address']}"
    return "Fawry"


def _require_payer(user):
    if user.role not in (User.Role.OWNER, User.Role.TENANT):
        raise PermissionDenied("Only owners and tenants have payment methods.")


class PaymentMethodListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="My saved payment methods", responses={200: PaymentMethodSerializer(many=True)})
    def get(self, request):
        _require_payer(request.user)
        methods = PaymentMethod.objects.filter(user=request.user)
        return Response(PaymentMethodSerializer(methods, many=True).data)

    @extend_schema(
        summary="Save a payment method (wallet, InstaPay or Fawry)",
        request=PaymentMethodCreateSerializer,
        responses={201: PaymentMethodSerializer},
    )
    def post(self, request):
        _require_payer(request.user)
        body = PaymentMethodCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        with transaction.atomic():
            mine = PaymentMethod.objects.select_for_update().filter(user=request.user)
            if mine.count() >= MAX_METHODS:
                return Response(
                    {"detail": f"You can save up to {MAX_METHODS} payment methods. Remove one first."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            identical = mine.filter(
                kind=data["kind"],
                wallet_provider=data.get("wallet_provider", ""),
                wallet_phone=data.get("wallet_phone", ""),
                instapay_address=data.get("instapay_address", ""),
            )
            if identical.exists():
                return Response({"detail": "You already saved this payment method."}, status=status.HTTP_400_BAD_REQUEST)

            # The first one saved becomes the default; otherwise only if asked.
            make_default = data.get("make_default") or not mine.exists()
            if make_default:
                mine.update(is_default=False)
            method = PaymentMethod.objects.create(
                user=request.user,
                kind=data["kind"],
                label=_label_for(data["kind"], data),
                wallet_provider=data.get("wallet_provider", ""),
                wallet_phone=data.get("wallet_phone", ""),
                instapay_address=data.get("instapay_address", ""),
                is_default=make_default,
            )
        return Response(PaymentMethodSerializer(method).data, status=status.HTTP_201_CREATED)


class PaymentMethodDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Remove a saved payment method", responses={204: None})
    def delete(self, request, pk):
        _require_payer(request.user)
        method = get_object_or_404(PaymentMethod, pk=pk, user=request.user)
        was_default = method.is_default
        method.delete()
        if was_default:
            # Keep one default whenever any method is left.
            nxt = PaymentMethod.objects.filter(user=request.user).first()
            if nxt is not None:
                nxt.is_default = True
                nxt.save(update_fields=["is_default"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentMethodDefaultView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Make a saved method my default", request=None, responses={200: PaymentMethodSerializer})
    def post(self, request, pk):
        _require_payer(request.user)
        with transaction.atomic():
            method = get_object_or_404(PaymentMethod.objects.select_for_update(), pk=pk, user=request.user)
            PaymentMethod.objects.filter(user=request.user).update(is_default=False)
            method.is_default = True
            method.save(update_fields=["is_default"])
        return Response(PaymentMethodSerializer(method).data)


class PaymentMethodOptionsView(APIView):
    """What can be added right now — so the app never offers something that can't work."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Which payment methods can be added")
    def get(self, request):
        _require_payer(request.user)
        # Cards need the gateway's secure form, which needs the village's
        # Paymob account. Until it is linked there is nothing to add a card to.
        card_ready = gateway_is_linked()
        return Response({
            "card": {"enabled": card_ready, "reason": "" if card_ready else "GATEWAY_NOT_LINKED"},
            "wallet": {"enabled": True, "providers": [{"value": v, "label": l} for v, l in PaymentMethod.Wallet.choices]},
            "instapay": {"enabled": True},
            "fawry": {"enabled": True},
            "max_methods": MAX_METHODS,
        })
