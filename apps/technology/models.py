# apps/technology/models.py
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.functional import cached_property
from django.utils import timezone
import json

CONF_CHOICES = (
    ("C1",  "C1-PUBLIC"),
    ("C2",  "C2-CONFIDENTIAL"),
    ("C3C", "C3-STRATEGIC (CIVIL)"),
    ("C3M", "C3-STRATEGIC (MILITARY)"),
)
CONFIDENTIALITY_CHOICES = CONF_CHOICES


def unique_slug(model_cls, name: str, instance=None, field_name: str = "slug") -> str:
    base = slugify(name) or "technology"
    slug = base
    i = 2
    qs = model_cls.objects.all()
    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(**{field_name: slug}).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


class Technology(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    # Long content sections (HTML list items produced by TinyMCE)
    desc_and_applications = models.TextField(blank=True)
    publications_and_projects = models.TextField(blank=True)
    attributes_and_performance = models.TextField(blank=True)
    strategic_value_and_evaluation = models.TextField(blank=True)
    enabling_technologies = models.TextField(blank=True)
    challenges_and_current_status = models.TextField(blank=True)

    # Hierarchy
    macro = models.CharField(max_length=120, blank=True, default="")
    meso1 = models.CharField(max_length=120, blank=True, default="")
    meso2 = models.CharField(max_length=120, blank=True, default="")

    # Meta
    initial_date = models.DateTimeField(default=timezone.now)
    last_modified = models.DateTimeField(default=timezone.now)
    confidentiality = models.CharField(max_length=4, choices=CONF_CHOICES, default="C1")

    # JSON as text (safe for Djongo)
    # extra_fields: [{ "name": str, "content": html }]
    extra_fields = models.TextField(blank=True, default="[]")

    # gallery: [{ "name": str, "b64": "data:image/...;base64,...", "tag": "SC1|SC2|", "type": "upload|evaluation", "uploaded_at": iso-str }]
    gallery = models.TextField(blank=True, default="[]")

    evaluation_history = models.TextField(blank=True, default="[]")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    # slug kept unique
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        db_table = "technology_technology"
        ordering = ("-created_at",)

    def get_absolute_url(self):
        return reverse("technology_detail", kwargs={"pk": self.pk})

    # ---- helpers to work with JSON text fields ----
    @staticmethod
    def _loads(s, default):
        try:
            return json.loads(s or "") if s else default
        except Exception:
            return default

    @staticmethod
    def _dumps(obj):
        return json.dumps(obj, ensure_ascii=False)

    @property
    def extra_fields_list(self):
        return Technology._loads(self.extra_fields, [])

    def set_extra_fields(self, items):
        self.extra_fields = Technology._dumps(items)

    @property
    def gallery_list(self):
        return Technology._loads(self.gallery, [])    

    def set_gallery(self, items):
        self.gallery = Technology._dumps(items)

    def save(self, *args, **kwargs):
        self.last_modified = timezone.now()
        needs_slug = not self.slug
        if self.pk and not needs_slug:
            try:
                orig = Technology.objects.only("name", "slug").get(pk=self.pk)
                if orig.name != self.name:
                    needs_slug = True
            except Technology.DoesNotExist:
                needs_slug = True
        if needs_slug:
            self.slug = unique_slug(Technology, self.name, instance=self)
        super().save(*args, **kwargs)

    @cached_property
    def card_image_b64(self) -> str:
        """
        Prefer a gallery image tagged with SC1 (case-insensitive).
        If none, fall back to the first valid image. Returns data-URI or ''.
        """
        items = self.gallery_list or []

        def is_image_b64(x):
            b64 = (x or {}).get("b64") or ""
            return isinstance(b64, str) and b64.startswith("data:image")

        # 1) look for SC1-tagged image
        for g in items:
            tag = (g or {}).get("tag") or ""
            if "sc1" in tag.lower() and is_image_b64(g):
                return g["b64"]

        # 2) fallback: first image
        for g in items:
            if is_image_b64(g):
                return g["b64"]

        return ""    

