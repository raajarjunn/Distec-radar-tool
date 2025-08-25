from django.db import migrations
import json, os

def load_roles(apps, schema_editor):
    Role = apps.get_model('authentication', 'Role')
    base_dir = os.path.dirname(os.path.dirname(__file__))  # migrations -> authentication
    roles_file = os.path.join(base_dir, 'roles.json')
    if not os.path.exists(roles_file):
        return
    with open(roles_file, 'r') as f:
        items = json.load(f)
    for r in items:
        Role.objects.get_or_create(
            name=r['name'],
            defaults={'description': r.get('description', '')}
        )

class Migration(migrations.Migration):
    dependencies = [
        ('authentication', '0001_initial'),
    ]
    operations = [migrations.RunPython(load_roles)]
