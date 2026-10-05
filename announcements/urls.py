from django.urls import path

from .views import AnnouncementImageView, AnnouncementListView

app_name = "announcements"

urlpatterns = [
    path("api/announcements/", AnnouncementListView.as_view(), name="list"),
    path("api/announcements/<int:pk>/image/", AnnouncementImageView.as_view(), name="image"),
]
