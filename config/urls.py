from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from core.public_views import ResortListView
from users.views import ActivateView, MeView, GenerateActivationCodeView, FirebaseAuthView, FCMTokenRegisterView
from billing.views import (
    ChargeDeferView,
    ChargeSummaryView,
    ClearanceGenerateView,
    ClearanceListView,
    ClearancePdfDownloadView,
    OwnerChargeListView,
    OwnerPaymentHistoryView,
    PaymentPlanListCreateView,
    PaymentReceiptDownloadView,
)
from collections_app.api_views import InitiateOnlinePaymentAPIView, PaymentWebhookAPIView
from core.views import unit_statement_view, unit_search_view, unit_detail_view
from core.notification_views import (
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationUnreadCountView,
)
from collections_app.views import daily_collections_view, record_payment_view


urlpatterns = [
    # Custom admin views
    path("admin/unit-search/", unit_search_view, name="unit_search"),
    path("admin/unit-detail/<int:unit_id>/", unit_detail_view, name="unit_detail"),
    path("admin/daily-collections/", daily_collections_view, name="daily_collections"),
    path("admin/record-payment/", record_payment_view, name="record_payment"),
    path("admin/messenger/", include("messenger.urls", namespace="messenger")),

    path("admin/", admin.site.urls),

    # API schema/docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),

    # Auth & FCM APIs
    path("api/auth/activate/", ActivateView.as_view(), name="activate"),
    path("api/auth/firebase/", FirebaseAuthView.as_view(), name="firebase_auth"),
    path("api/auth/fcm-token/", FCMTokenRegisterView.as_view(), name="fcm_token_register"),
    path("api/auth/generate-code/", GenerateActivationCodeView.as_view(), name="generate_code"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Public
    path("api/resorts/", ResortListView.as_view(), name="resort_list"),

    # Profile, Charges & Payments APIs
    path("api/me/", MeView.as_view(), name="me"),
    path("api/charges/", OwnerChargeListView.as_view(), name="owner_charges"),
    path("api/charges/summary/", ChargeSummaryView.as_view(), name="charges_summary"),
    path("api/charges/<int:pk>/defer/", ChargeDeferView.as_view(), name="charge_defer"),
    path("api/payment-plans/", PaymentPlanListCreateView.as_view(), name="payment_plans"),
    path("api/clearance/generate/", ClearanceGenerateView.as_view(), name="clearance_generate"),
    path("api/clearance/", ClearanceListView.as_view(), name="clearance_list"),
    path("api/clearance/<int:pk>/pdf/", ClearancePdfDownloadView.as_view(), name="clearance_pdf_download"),
    path("api/payments/", OwnerPaymentHistoryView.as_view(), name="owner_payments"),
    path("api/payments/<int:pk>/receipt/", PaymentReceiptDownloadView.as_view(), name="payment_receipt_download"),
    path("api/payments/initiate/", InitiateOnlinePaymentAPIView.as_view(), name="initiate_payment"),
    path("api/payments/webhook/", PaymentWebhookAPIView.as_view(), name="payment_webhook"),

    # Support & Gate/Beach Pass APIs
    path("", include("support.urls")),

    # Resort feed (staff-authored announcements, listings, events)
    path("", include("announcements.urls")),

    # Notifications API
    path("api/notifications/", NotificationListView.as_view(), name="notification_list"),
    path("api/notifications/<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification_mark_read"),
    path("api/notifications/mark-all-read/", NotificationMarkAllReadView.as_view(), name="notification_mark_all_read"),
    path("api/notifications/unread-count/", NotificationUnreadCountView.as_view(), name="notification_unread_count"),

    # Admin statement
    path("admin/unit-statement/<int:unit_id>/", unit_statement_view, name="unit_statement"),
]

if settings.DEBUG:
    # Mirrors nginx.conf in production: only resort branding is public.
    # Receipts/clearance PDFs/ticket attachments must go through their
    # authenticated download views even in dev, or this fix would only ever
    # be exercised in production and never actually tested locally.
    urlpatterns += static(
        settings.MEDIA_URL + "resort_logos/",
        document_root=str(settings.MEDIA_ROOT / "resort_logos"),
    )