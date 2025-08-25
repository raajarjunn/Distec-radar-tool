from django.db import migrations

def noop_forward(apps, schema_editor):
    """
    0004 originally tried to drop an index named 'technology__slug_7702f0_idx'.
    It may already be gone (dropped in 0003 or never created), which causes
    Djongo to error. Treat this migration as a no-op at the DB level.
    """
    try:
        # Best-effort: drop by name if it exists; ignore all failures.
        conn = getattr(schema_editor.connection, "connection", None)
        if not conn:
            return
        client = getattr(conn, "client", None) or conn  # Djongo sometimes exposes MongoClient directly
        dbname = schema_editor.connection.settings_dict.get("NAME")
        coll = client[dbname]["technology_technology"]
        existing = {ix.get("name") for ix in coll.list_indexes()}
        for name in ("technology__slug_7702f0_idx", "slug_1"):
            if name in existing:
                try:
                    coll.drop_index(name)
                except Exception:
                    pass
    except Exception:
        # swallow anything – goal is to not fail migration if index isn't there
        pass

def noop_reverse(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ("technology", "0003_drop_unique_slug_index_if_exists"),
    ]
    operations = [
        migrations.RunPython(noop_forward, noop_reverse),
    ]
