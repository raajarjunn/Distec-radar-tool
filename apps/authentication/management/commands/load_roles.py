from django.core.management.base import BaseCommand
from apps.authentication.models import Role
import json
import os
from django.conf import settings

class Command(BaseCommand):
    help = "Load roles from roles.json into the database"

    def handle(self, *args, **kwargs):
        file_path = os.path.join(settings.BASE_DIR, "apps/authentication/roles.json")
        with open(file_path, "r") as f:
            roles = json.load(f)

        for role_data in roles:
            role, created = Role.objects.get_or_create(
                name=role_data["name"],
                defaults={"description": role_data.get("description", "")}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Role created: {role.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Role already exists: {role.name}"))
