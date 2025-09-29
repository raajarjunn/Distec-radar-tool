# G:\Master Thesis\Application\Main\Distec\apps\authentication\migrations\0004_auto_20250809_0432.py

import bson.objectid
from django.db import migrations
import djongo.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_load_access_policies'),
    ]

    operations = [
        migrations.AlterField(
            model_name='role',
            name='id',
            field=djongo.models.fields.ObjectIdField(auto_created=True, default=bson.objectid.ObjectId, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='user',
            name='id',
            field=djongo.models.fields.ObjectIdField(auto_created=True, default=bson.objectid.ObjectId, primary_key=True, serialize=False),
        ),
    ]
