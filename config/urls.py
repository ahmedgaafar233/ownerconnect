from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from users.views import ActivateView, MeView, GenerateActivationCodeView
from billing.views import OwnerChargeListView
from core.views import unit_statement_view, unit_search_view, unit_detail_view
from collections_app.views import daily_collections_view, record_payment_view


urlpatterns = [
    # Custom admin views (must be before admin.site.urls)
    path("admin/unit-search/", unit_search_view, name="unit_search"),
    path("admin/unit-detail/<int:unit_id>/", unit_detail_view, name="unit_detail"),
    path("admin/daily-collections/", daily_collections_view, name="daily_collections"),
    path("admin/record-payment/", record_payment_view, name="record_payment"),
    path("admin/messenger/", include("messenger.urls", namespace="messenger")),

    path("admin/", admin.site.urls),

    # API schema/docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),

    # Auth
    path("api/auth/activate/", ActivateView.as_view(), name="activate"),
    path("api/auth/generate-code/", GenerateActivationCodeView.as_view(), name="generate_code"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Me + Charges
    path("api/me/", MeView.as_view(), name="me"),
    path("api/charges/", OwnerChargeListView.as_view(), name="owner_charges"),

    # Admin statement (print/save PDF from browser)
    path("admin/unit-statement/<int:unit_id>/", unit_statement_view, name="unit_statement"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)