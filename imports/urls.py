from django.urls import path
from .views import ImportWizardView

urlpatterns = [
    path("wizard/", ImportWizardView.as_view(), name="import_wizard"),
]
