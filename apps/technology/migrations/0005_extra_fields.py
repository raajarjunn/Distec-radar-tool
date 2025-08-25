# apps/technology/migrations/0005_extra_fields.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('technology', '0004_auto_20250813_1534'),  # or your latest
    ]
    operations = [
        migrations.AddField(
            model_name='technology',
            name='extra_fields',
            field=models.TextField(blank=True, default=[]),
        ),
    ]
