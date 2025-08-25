from django.urls import path
from .views import profile_view, delete_account, profile_dump, ping
from . import views

urlpatterns = [
    path("", profile_view, name="profile"),            # /profile/
    path("delete/", delete_account, name="profile_delete"),
    path("avatar/<str:user_id>/", views.profile_avatar, name="profile_avatar"),
    path("debug/", profile_dump, name="profile_dump"),  # JSON debug
    path("ping/", ping, name="profile_ping")   # /profile/ping/
]
