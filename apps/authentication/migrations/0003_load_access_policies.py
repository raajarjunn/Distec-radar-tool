from django.db import migrations
import json, os

def load_access_policies(apps, schema_editor):
    Role = apps.get_model('authentication', 'Role')
    RolePermission = apps.get_model('authentication', 'RolePermission')

    base_dir = os.path.dirname(os.path.dirname(__file__))  # migrations -> authentication
    policies_file = os.path.join(base_dir, 'access_policies.json')
    if not os.path.exists(policies_file):
        return

    with open(policies_file, 'r') as f:
        policies = json.load(f)

    for role_name, perms in policies.items():
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            continue
        for perm in perms:
            RolePermission.objects.get_or_create(role=role, permission=perm)

class Migration(migrations.Migration):
    dependencies = [
        ('authentication', '0002_load_roles'),
    ]
    operations = [migrations.RunPython(load_access_policies)]
