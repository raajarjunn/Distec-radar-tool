# apps/technology/migrations/0003_drop_unique_slug_index_if_exists.py
from django.db import migrations

def drop_problem_indexes(apps, schema_editor):
    """
    Djongo sometimes leaves/creates a unique index on 'slug' (e.g. 'slug_1')
    or Django names like 'technology__slug_..._idx'. Drop them if they exist,
    then (re)create a non-unique index on 'slug'.
    """
    try:
        # Djongo exposes PyMongo through the cursor
        db = schema_editor.connection.cursor().db_conn
    except Exception:
        try:
            from django.db import connection
            db = connection.cursor().db_conn
        except Exception:
            db = None

    if not db:
        return

    coll = db['technology_technology']

    # collect existing index names (works on most PyMongo versions)
    try:
        names = {i.get('name') for i in coll.list_indexes()}
    except Exception:
        try:
            info = coll.index_information()
            names = set(info.keys()) | {v.get('name') for v in info.values()}
        except Exception:
            names = set()

    candidates = {
        'slug_1',
        'slug_1_unique',
        'technology__slug_7702f0_idx',   # example Django-generated name
    }

    for nm in candidates:
        if nm and nm in names:
            try:
                coll.drop_index(nm)
            except Exception:
                pass

    # ensure we have a normal (non-unique) index on slug; sparse is fine
    try:
        coll.create_index('slug', name='slug_1', unique=False, sparse=True)
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('technology', '0002_backfill_arrays_and_slugs'),
    ]

    operations = [
        migrations.RunPython(drop_problem_indexes, migrations.RunPython.noop),
    ]
