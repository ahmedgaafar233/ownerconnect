from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from users.views import ActivateView, MeView, GenerateActivationCodeView, FirebaseAuthView, FCMTokenRegisterView
from billing.views import ChargeDeferView, OwnerChargeListView, OwnerPaymentHistoryView, PaymentPlanListCreateView
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

    # Profile, Charges & Payments APIs
    path("api/me/", MeView.as_view(), name="me"),
    path("api/charges/", OwnerChargeListView.as_view(), name="owner_charges"),
    path("api/charges/<int:pk>/defer/", ChargeDeferView.as_view(), name="charge_defer"),
    path("api/payment-plans/", PaymentPlanListCreateView.as_view(), name="payment_plans"),
    path("api/payments/", OwnerPaymentHistoryView.as_view(), name="owner_payments"),
    path("api/payments/initiate/", InitiateOnlinePaymentAPIView.as_view(), name="initiate_payment"),
    path("api/payments/webhook/", PaymentWebhookAPIView.as_view(), name="payment_webhook"),

    # Support & Gate/Beach Pass APIs
    path("", include("support.urls")),

    # Notifications API
    path("api/notifications/", NotificationListView.as_view(), name="notification_list"),
    path("api/notifications/<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification_mark_read"),
    path("api/notifications/mark-all-read/", NotificationMarkAllReadView.as_view(), name="notification_mark_all_read"),
    path("api/notifications/unread-count/", NotificationUnreadCountView.as_view(), name="notification_unread_count"),

    # Admin statement
    path("admin/unit-statement/<int:unit_id>/", unit_statement_view, name="unit_statement"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)