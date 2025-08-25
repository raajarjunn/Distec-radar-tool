from django.db import migrations
from django.utils.text import slugify
from django.core.exceptions import FieldDoesNotExist
import json


def normalize_arrays_and_slugs(apps, schema_editor):
    Technology = apps.get_model('technology', 'Technology')

    # Helpers to detect existence & type on the *historical* model
    def field_exists(name: str) -> bool:
        try:
            Technology._meta.get_field(name)
            return True
        except FieldDoesNotExist:
            return False

    def field_type(name: str) -> str:
        # Returns e.g. "TextField", "JSONField", ...
        try:
            return Technology._meta.get_field(name).get_internal_type()
        except Exception:
            return ""

    has_gallery = field_exists("gallery")
    has_eval    = field_exists("evaluation_history")

    gallery_is_text = field_type("gallery") == "TextField" if has_gallery else False
    eval_is_text    = field_type("evaluation_history") == "TextField" if has_eval else False

    # Build a set of existing slugs to avoid collisions
    existing = set(
        s for s in Technology.objects
        .exclude(slug__isnull=True).exclude(slug="")
        .values_list('slug', flat=True)
    )

    def to_list(value):
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                data = json.loads(value)
                return data if isinstance(data, list) else []
            except Exception:
                return []
        try:
            return list(value)
        except Exception:
            return []

    for obj in Technology.objects.all():
        changed_fields = []

        # Only touch gallery/evaluation_history if they exist on this historical model
        if has_gallery:
            current = getattr(obj, "gallery", [])
            normalized = to_list(current)
            # Write correct representation for the field's type
            new_val = json.dumps(normalized) if gallery_is_text else normalized
            if current != new_val:
                setattr(obj, "gallery", new_val)
                changed_fields.append("gallery")

        if has_eval:
            current = getattr(obj, "evaluation_history", [])
            normalized = to_list(current)
            new_val = json.dumps(normalized) if eval_is_text else normalized
            if current != new_val:
                setattr(obj, "evaluation_history", new_val)
                changed_fields.append("evaluation_history")

        # Backfill slug if missing
        if not getattr(obj, "slug", ""):
            base = slugify(getattr(obj, "name", "") or "") or "technology"
            slug = base
            i = 2
            while slug in existing:
                slug = f"{base}-{i}"
                i += 1
            setattr(obj, "slug", slug)
            existing.add(slug)
            changed_fields.append("slug")

        if changed_fields:
            # last_modified might not exist historically; ignore if absent
            if hasattr(obj, "last_modified"):
                changed_fields.append("last_modified")
            try:
                obj.save(update_fields=list(set(changed_fields)))
            except TypeError:
                # On very old Django versions or Djongo quirks,
                # update_fields may not be accepted — fall back to full save.
                obj.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('technology', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(normalize_arrays_and_slugs, noop_reverse),
    ]
