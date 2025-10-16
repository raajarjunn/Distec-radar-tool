# apps/technology/forms.py
from django import forms
from .models import Technology
import unicodedata


class TechnologyForm(forms.ModelForm):
    # helper inputs when user chooses “+ Add new”
    new_macro = forms.CharField(required=False)
    new_meso1 = forms.CharField(required=False)
    new_meso2 = forms.CharField(required=False)

    # (field_name, dom_id, human_label, limit) – limits used by your JS only
    BULLET_FIELDS = [
        ("desc_and_applications",        "editor-desc",  "Descriptions and applications", 960),
        ("publications_and_projects",    "editor-pub",   "Publication and projects",      700),
        ("attributes_and_performance",   "editor-attr",  "Attributes and performance",    700),
        ("strategic_value_and_evaluation","editor-strat","Strategic value and evaluation",700),
        ("enabling_technologies",        "editor-enab",  "Enabling Technologies",         680),
        ("challenges_and_current_status","editor-chal",  "Challenges and current status", 960),
    ]

    class Meta:
        model = Technology
        fields = [
            "name", "description",
            "macro", "meso1", "meso2",
            "desc_and_applications", "publications_and_projects",
            "attributes_and_performance", "strategic_value_and_evaluation",
            "enabling_technologies", "challenges_and_current_status",
            "confidentiality", "is_active",
        ]
        widgets = {
            "name":  forms.TextInput(attrs={"class": "form-control", "style": "text-transform:uppercase;"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),

            # We render our own cascading <select>s in the template
            "macro": forms.TextInput(attrs={"class": "d-none"}),
            "meso1": forms.TextInput(attrs={"class": "d-none"}),
            "meso2": forms.TextInput(attrs={"class": "d-none"}),

            # Long text areas; TinyMCE class/ids are added in __init__ (edit mode only)
            "desc_and_applications":        forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "publications_and_projects":    forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "attributes_and_performance":   forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "strategic_value_and_evaluation": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "enabling_technologies":        forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "challenges_and_current_status": forms.Textarea(attrs={"class": "form-control", "rows": 6}),

            "confidentiality": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    # ---------- ADD THIS ----------
    def clean_name(self):
        """
        Enforce case-insensitive uniqueness on Technology.name.
        - Trims whitespace
        - Normalizes Unicode so visually identical names compare equal
        - Ignores the current instance when editing
        """
        raw = self.cleaned_data.get("name") or ""
        # Normalize & trim to avoid sneaky duplicates like “Tech ” vs “Tech”
        name = unicodedata.normalize("NFC", raw).strip()

        norm = unicodedata.normalize("NFC", raw).strip()
        upper = norm.upper()  

        # Case-insensitive duplicate check
        qs = Technology.objects.filter(name__iexact=upper)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A technology with this name already exists.")

        return upper
    
    # ---------- /ADD THIS ----------

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ensure consistent bootstrap classes on basic inputs/selects
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.TextInput, forms.Textarea, forms.Select)):
                css = (w.attrs.get("class") or "").strip()
                if "form-control" in css or "d-none" in css:
                    continue
                w.attrs["class"] = (css + " form-control").strip()

        # TinyMCE bullet editors only in EDIT mode
        if self.instance and self.instance.pk:
            for fname, dom_id, label, _limit in self.BULLET_FIELDS:
                w = self.fields[fname].widget
                # keep any existing classes and add our hook
                w.attrs["class"] = (w.attrs.get("class", "") + " tinymce-bullets").strip()
                w.attrs["id"] = dom_id
                w.attrs["data-fieldname"] = label

        # Make sure the checkbox has a stable id for the label
        self.fields["is_active"].widget.attrs.setdefault("id", "is_active_switch")

    def clean(self):
        cleaned = super().clean()

        macro  = (cleaned.get("macro") or "").strip()
        meso1  = (cleaned.get("meso1") or "").strip()
        meso2  = (cleaned.get("meso2") or "").strip()

        n_macro = (cleaned.get("new_macro") or "").strip()
        n_meso1 = (cleaned.get("new_meso1") or "").strip()
        n_meso2 = (cleaned.get("new_meso2") or "").strip()

        # If user selected "+ Add new", replace with the typed value.
        if macro == "__new__" or (not macro and n_macro):
            macro = n_macro
        if meso1 == "__new__" or (not meso1 and n_meso1):
            meso1 = n_meso1
        if meso2 == "__new__" or (not meso2 and n_meso2):
            meso2 = n_meso2

        cleaned["macro"] = macro
        cleaned["meso1"] = meso1
        cleaned["meso2"] = meso2
        return cleaned
