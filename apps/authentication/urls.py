# Distec\apps\authentication\urls.py
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from .views import login_view, register_user
from django.contrib.auth.views import LogoutView
from apps.authentication.views import UserRoleListView, UserRoleUpdateView, UserRoleDeleteView


urlpatterns = [
    path('login/', login_view, name="login"),
    path('register/', register_user, name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),

    path("role-admin/", UserRoleListView.as_view(), name="role_admin_list"),
    path("role-admin/<str:pk>/", UserRoleUpdateView.as_view(), name="role_admin_edit"),

    path("role-admin/users/<str:pk>/delete/", UserRoleDeleteView.as_view(), name="admin_user_delete"),
  



]

