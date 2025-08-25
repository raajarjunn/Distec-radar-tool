# apps/authentication/apps.py
from django.apps import AppConfig

class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.authentication"

    def ready(self):
        # Import signals when the app is ready
        from . import signals  # noqa

# TEMP: prevent crash on login while PK issue is fixed
        from django.contrib.auth.signals import user_logged_in
        from django.contrib.auth.models import update_last_login
        user_logged_in.disconnect(update_last_login)