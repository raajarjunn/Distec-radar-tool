from django.contrib.auth.models import AbstractUser
from django.db import models
from .role import Role

class User(AbstractUser):
    isSuperAdmin = models.BooleanField(default=False)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)

    def get_role_name(self):
        return self.role.name if self.role else None

    def has_permission(self, action):
        """
        Check if this user has the given action permission
        based on access_policies.json.
        """
        from django.conf import settings
        import json, os

        policy_path = os.path.join(settings.BASE_DIR, "apps/authentication/access_policies.json")
        with open(policy_path, "r") as f:
            policies = json.load(f)

        role_name = self.get_role_name()
        if not role_name:
            return False

        allowed_actions = policies.get(role_name, [])
        return action in allowed_actions or self.isSuperAdmin
