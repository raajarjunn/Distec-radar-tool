# apps/technology/views.py
import csv
import json
import datetime
import base64
import imghdr

from apps.common.activity_log import log_activity

# User permissions
from apps.authentication.perm import user_has_permission, require_action
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest


from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import DatabaseError, IntegrityError
from django.db.models import Q, Case, When, IntegerField
from django.http import (
    HttpResponse, JsonResponse, HttpResponseRedirect, Http404
)
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.utils.text import get_valid_filename

from .models import Technology, CONFIDENTIALITY_CHOICES
from .forms import TechnologyForm


# MindMap functions
import json
from collections import defaultdict
from django.shortcuts import render
from .models import Technology
from pymongo import MongoClient

#evaluation
import os, json, base64, re, tempfile, shutil
from urllib.parse import quote
import numpy as np
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from .models import Technology
from django.utils import timezone



# Scorecard
from bson import ObjectId
from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.timezone import make_aware, is_naive, localtime
from django.utils.safestring import mark_safe
from django.views.decorators.clickjacking import xframe_options_sameorigin





#Compendium
from pymongo import MongoClient 
from pymongo.errors import ServerSelectionTimeoutError
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404
from .models import Technology
from datetime import datetime
from django.template.loader import render_to_string
from django.utils.timezone import make_aware, localtime

from zoneinfo import ZoneInfo
BERLIN = ZoneInfo("Europe/Berlin")



#-------------Pymongo defined--------------------------

client = MongoClient("mongodb://localhost:27017/")
db = client["tech_tool_db"]
technologies = db["technology_technology"] 
qualifications = db["qualifications"]



# -------------------------- small helpers --------------------------

# Back-compat helpers (keep if you still receive ?active=1/0)
_TRUTHY = {"1", "true", "t", "yes", "y", "on", "active"}
_FALSY  = {"0", "false", "f", "no", "n", "off", "inactive"}

def _loads(text):
    try:
        return json.loads(text or "[]")
    except Exception:
        return []

def _dumps(py):
    return json.dumps(py, ensure_ascii=False)

def _redirect_back_to_edit(request, pk):
    # Prefer returning to the edit page; fall back to detail if referer missing.
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", f"/technology/{pk}/edit/"))

# NEW: parse status (multi-select). Falls back to legacy ?active=1/0.
def _parse_status(request):
    statuses = [s.strip().lower() for s in request.GET.getlist("status") if s.strip()]
    if statuses:
        return True, statuses

    # Back-compat: map old ?active=1/0 to status values
    active_flags = {(v or "").strip().lower() for v in request.GET.getlist("active")}
    has_true = bool(active_flags & _TRUTHY)
    has_false = bool(active_flags & _FALSY)
    sel = []
    if has_true:
        sel.append("active")
    if has_false:
        sel.append("inactive")
    return (bool(sel), sel) if sel else (False, [])

def _normalized_category_list():
    """
    One de-duplicated list of taxonomy strings (macro/meso1/meso2).
    Avoids QuerySet unions across different fields for Djongo safety.
    """
    raw_vals = list(Technology.objects.values_list("macro", flat=True)) \
             + list(Technology.objects.values_list("meso1", flat=True)) \
             + list(Technology.objects.values_list("meso2", flat=True))
    cleaned = {(s or "").strip() for s in raw_vals if (s or "").strip()}
    return sorted(cleaned, key=str.lower)

def _stable_key_created_desc(obj):
    # secondary key for consistent ordering
    dt = getattr(obj, "created_at", None) or datetime.min
    # Python sorts ascending, so use negative timestamp-like number
    return -int(dt.timestamp()) if hasattr(dt, "timestamp") else 0

# NEW: Python-side status sorter (Djongo-safe).
def _python_sort_status(iterable, priority=("active", "dormant", "inactive")):
    """
    Group by status using priority order, then sort within each group by:
      - created_at desc
      - name asc (case-insensitive)
    Unknown/empty statuses go to the end.
    """
    items = list(iterable)
    buckets = {key: [] for key in priority}
    others = []
    for x in items:
        s = (getattr(x, "status", "") or "").lower()
        if s in buckets:
            buckets[s].append(x)
        else:
            others.append(x)  # unknowns last

    def group_sort(lst):
        return sorted(
            lst,
            key=lambda o: (
                _stable_key_created_desc(o),           # created_at desc
                (getattr(o, "name", "") or "").lower() # name asc tiebreaker
            )
        )

    out = []
    for key in priority:
        out.extend(group_sort(buckets[key]))
    out.extend(group_sort(others))
    return out

def apply_filters_and_sort(request, qs):
    # -------- Search
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(macro__icontains=q) |
            Q(meso1__icontains=q) |
            Q(meso2__icontains=q) |
            Q(description__icontains=q)
        )

    # -------- Category filter
    selected_categories = [c.strip() for c in request.GET.getlist("categories") if c.strip()]
    if selected_categories:
        qcat = Q()
        for c in selected_categories:
            qcat |= Q(macro__iexact=c) | Q(meso1__iexact=c) | Q(meso2__iexact=c)
        qs = qs.filter(qcat)

    # -------- Status filter (multi-select, with back-compat)
    has_filter, status_selected = _parse_status(request)
    if has_filter and status_selected:
        qs = qs.filter(status__in=status_selected)

    # -------- Sort
    sort = (request.GET.get("sort") or "created_desc").strip()

    # Djongo-safe: do Python sorts for status-first options
    if sort == "status_active_first":
        return _python_sort_status(qs, priority=("active", "dormant", "inactive"))
    if sort == "status_inactive_first":
        return _python_sort_status(qs, priority=("inactive", "dormant", "active"))
    if sort == "status_dormant_first":
        return _python_sort_status(qs, priority=("dormant", "active", "inactive"))

    # DB-side sort for the safe cases
    ordering_map = {
        "name_asc": "name",
        "name_desc": "-name",
        "created_asc": "created_at",
        "created_desc": "-created_at",
    }
    return qs.order_by(ordering_map.get(sort, "-created_at"))


# -------------------------- list / details --------------------------

class TechnologyListView(LoginRequiredMixin, ListView):
    required_action = "view_technology"
    model = Technology
    template_name = "technology/list.html"
    context_object_name = "items"
    paginate_by = 12

    def get_queryset(self):
        return apply_filters_and_sort(self.request, super().get_queryset())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["segment"] = "technology"
        ctx["view_mode"] = (self.request.GET.get("view") or "cards").strip()
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["all_categories"] = _normalized_category_list()
        ctx["selected_categories"] = [c for c in self.request.GET.getlist("categories") if c.strip()]

        # NEW: expose selected statuses (used by checkboxes in the template)
        _, status_selected = _parse_status(self.request)
        ctx["status_selected"] = status_selected

        ctx["sort"] = (self.request.GET.get("sort") or "created_desc").strip()
        SORT_LABELS = {
            "created_desc": "Newest",
            "created_asc": "Oldest",
            "name_asc": "Name A→Z",
            "name_desc": "Name Z→A",
            "status_active_first": "Active first",
            "status_inactive_first": "Inactive first",
            "status_dormant_first": "Dormant first",
        }
        ctx["sort_label"] = SORT_LABELS.get(ctx["sort"], "Newest")
        return ctx



class TechnologyDetailView(LoginRequiredMixin, DetailView):
    required_action = "view_technology"
    model = Technology
    template_name = "technology/detail.html"
    pk_url_kwarg = "pk"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        # Make JSON strings usable in the template
        def _loads(s):
            try:
                return json.loads(s or "[]")
            except Exception:
                return []
        ctx["gallery"] = _loads(getattr(obj, "gallery", "[]"))
        ctx["extra_fields"] = _loads(getattr(obj, "extra_fields", "[]"))
        return ctx


class TechnologyCreateView(LoginRequiredMixin, CreateView):
    required_action = "add_technology"
    model = Technology
    form_class = TechnologyForm
    template_name = "technology/create.html"
    success_url = reverse_lazy("technology_list")

# acitvity log
    def form_valid(self, form):
        resp = super().form_valid(form)  # self.object now saved
        log_activity(
            username=self.request.user.get_username(),
            activity="Add technology",
            logged_in=True,
            meta={"technology_id": str(self.object.pk), "technology_name": self.object.name},
        )
        messages.success(self.request, "Technology created successfully.")
        return resp



class TechnologyUpdateView(LoginRequiredMixin, UpdateView):
    required_action = "edit_technology"
    model = Technology
    form_class = TechnologyForm
    template_name = "technology/create.html"  # reuse same page
    pk_url_kwarg = "pk"
    context_object_name = "object"

    def form_valid(self, form):
        try:
            resp = super().form_valid(form)
#actvity log
            log_activity(
                username=self.request.user.get_username(),
                activity="Edit technology",
                logged_in=True,
                meta={"technology_id": str(self.object.pk), "technology_name": self.object.name},
            )
            messages.success(self.request, "Technology updated successfully.")
            return resp
        except (IntegrityError, DatabaseError) as e:
            # Djongo duplicate-key ends up as DatabaseError; show a clean message
            msg = str(e)
            if "duplicate key" in msg.lower() or "e11000" in msg.lower():
                form.add_error("name", "This name is already used by another technology.")
                return self.form_invalid(form)
            raise

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        # Parse JSON strings so the template can iterate/print safely
        gallery_json = getattr(obj, "gallery", "[]")
        extra_json = getattr(obj, "extra_fields", "[]")
        ctx["gallery"] = _loads(gallery_json)
        ctx["extra_fields"] = _loads(extra_json)
        return ctx


class TechnologyDeleteView(LoginRequiredMixin, DeleteView):
    required_action = "delete_technology"
    model = Technology
    template_name = "technology/confirm_delete.html"  # unused; we submit via modal
    pk_url_kwarg = "pk"
    success_url = reverse_lazy("technology_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        confirm_name = (request.POST.get("confirm_name") or "").strip()
        if confirm_name != self.object.name:
            messages.error(request, "Deletion aborted: name did not match.")
            return redirect(self.object.get_absolute_url())
        return super().post(request, *args, **kwargs)


#log activity
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        tech_id, tech_name = str(self.object.pk), self.object.name
        resp = super().delete(request, *args, **kwargs)
        log_activity(
            username=request.user.get_username(),
            activity="Delete technology",
            logged_in=True,
            meta={"technology_id": tech_id, "technology_name": tech_name},
        )
        messages.success(request, "Technology deleted.")
        return resp

# -------------------------- taxonomy JSON APIs --------------------------

@require_GET
@require_action("view_technology")
def api_macros(request):
    rows = (Technology.objects
            .exclude(macro="")
            .values_list("macro", flat=True)
            .distinct().order_by("macro"))
    return JsonResponse([{"name": m} for m in rows], safe=False)

@require_POST
@require_action("view_technology")
def api_meso1(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    macro = (data.get("macro") or "").replace("\u00A0", " ").strip()
    if not macro:
        return HttpResponseBadRequest("Missing macro")
    rows = (Technology.objects
            .filter(macro=macro)
            .exclude(meso1="")
            .values_list("meso1", flat=True)
            .distinct().order_by("meso1"))
    return JsonResponse([{"name": m} for m in rows], safe=False)

@require_POST
@require_action("view_technology")
def api_meso2(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    meso1 = (data.get("meso1") or "").replace("\u00A0", " ").strip()
    if not meso1:
        return HttpResponseBadRequest("Missing meso1")
    rows = (Technology.objects
            .filter(meso1=meso1)
            .exclude(meso2="")
            .values_list("meso2", flat=True)
            .distinct().order_by("meso2"))
    return JsonResponse([{"name": m} for m in rows], safe=False)



# -------------------------- Extra fields (add/edit/delete) --------------------------

@require_POST
@require_action("edit_technology")
def add_extra_field(request, pk):
    tech = get_object_or_404(Technology, pk=pk)
    name = (request.POST.get("field_name") or "").strip()
    content = request.POST.get("field_content") or ""
    if not name:
        return _redirect_back_to_edit(request, pk)

    fields = _loads(getattr(tech, "extra_fields", "[]"))
    fields.append({"name": name, "content": content})
    tech.extra_fields = _dumps(fields)
    tech.save(update_fields=["extra_fields"])
    messages.success(request, f'Field "{name}" added.')
    return _redirect_back_to_edit(request, pk)

@require_POST
@require_action("edit_technology")
def edit_extra_field(request, pk, index: int):
    tech = get_object_or_404(Technology, pk=pk)
    fields = _loads(getattr(tech, "extra_fields", "[]"))
    if index < 0 or index >= len(fields):
        raise Http404("Field not found")
    fields[index]["content"] = request.POST.get("field_content") or ""
    tech.extra_fields = _dumps(fields)
    tech.save(update_fields=["extra_fields"])
    messages.success(request, f'Field "{fields[index]["name"]}" updated.')
    return _redirect_back_to_edit(request, pk)

@require_POST
@require_action("delete_technology")
def delete_extra_field(request, pk, index: int):
    tech = get_object_or_404(Technology, pk=pk)
    fields = _loads(getattr(tech, "extra_fields", "[]"))
    if 0 <= index < len(fields):
        removed = fields.pop(index)
        tech.extra_fields = _dumps(fields)
        tech.save(update_fields=["extra_fields"])
        messages.success(request, f'Field "{removed.get("name","")}" deleted.')
    return _redirect_back_to_edit(request, pk)


# -------------------------- Gallery (base64) --------------------------

def _file_to_data_uri(django_file):
    """Read an uploaded file and return data URI (data:image/<kind>;base64,<...>)."""
    raw = b"".join(chunk for chunk in django_file.chunks())
    kind = imghdr.what(None, h=raw) or "png"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/{kind};base64,{b64}"

@require_POST
@require_action("edit_technology")
def add_gallery_image(request, pk):
    """
    Save uploaded image as base64 in Technology.gallery
    gallery item shape:
      {
        "name": "<original filename>",
        "b64": "data:image/png;base64,....",
        "tag": "SC1|SC2|",
        "type": "upload",
        "uploaded_at": "<iso8601>"
      }
    """
    tech = get_object_or_404(Technology, pk=pk)
    img = request.FILES.get("image")
    if not img:
        messages.error(request, "No image uploaded.")
        return _redirect_back_to_edit(request, pk)

    # (optional) small guardrails
    # if img.size > 10 * 1024 * 1024:
    #     messages.error(request, "Image too large (max 10 MB).")
    #     return _redirect_back_to_edit(request, pk)

    tag = (request.POST.get("tag") or "").strip()

    original_name = getattr(img, "name", "") or ""
    original_name = os.path.basename(original_name)  # strip any path bits
    original_name = get_valid_filename(original_name)  # keep it filesystem/URL friendly

    # fallback name if upload has no name
    if not original_name:
        original_name = f"img_{timezone.now().strftime('%Y%m%d%H%M%S')}"

    safe_name = original_name.strip()

    try:
        data_uri = _file_to_data_uri(img)
    except Exception as e:
        messages.error(request, f"Could not process the image: {e}")
        return _redirect_back_to_edit(request, pk)

    entry = {
        "name": safe_name,
        "b64": data_uri,
        "tag": tag,
        "type": "upload",
        # timezone-aware; with USE_TZ=True this is UTC and ISO 8601 (e.g., "2025-08-26T08:15:46+00:00")
        "uploaded_at": timezone.now().isoformat()
        # If you prefer a "Z" suffix, do: timezone.now().isoformat().replace("+00:00", "Z")
    }

    gallery = _loads(getattr(tech, "gallery", "[]"))
    # replace same name if exists
    gallery = [g for g in gallery if g.get("name") != safe_name]
    gallery.append(entry)

    tech.gallery = _dumps(gallery)
    tech.save(update_fields=["gallery"])
    messages.success(request, "Image uploaded.")
    return _redirect_back_to_edit(request, pk)


@require_POST
@require_action("edit_technology")
def update_gallery_tag(request, pk):
    tech = get_object_or_404(Technology, pk=pk)
    image_name = request.POST.get("image_name")
    new_tag = request.POST.get("tag", "")

    gallery = _loads(getattr(tech, "gallery", "[]"))

    # keep SC1 / SC2 unique
    if new_tag in ("SC1", "SC2"):
        for g in gallery:
            if g.get("tag") == new_tag:
                g["tag"] = ""

    updated = False
    for g in gallery:
        if g.get("name") == image_name:
            g["tag"] = new_tag
            updated = True
            break

    if updated:
        tech.gallery = _dumps(gallery)
        tech.save(update_fields=["gallery"])
        messages.success(request, "Tag updated.")
    else:
        messages.error(request, "Image not found.")

    return _redirect_back_to_edit(request, pk)


@require_POST
@require_action("delete_technology")
def delete_gallery_image(request, pk):
    tech = get_object_or_404(Technology, pk=pk)
    image_name = request.POST.get("image_name")

    gallery = _loads(getattr(tech, "gallery", "[]"))
    before = len(gallery)
    gallery = [g for g in gallery if g.get("name") != image_name]

    if len(gallery) < before:
        tech.gallery = _dumps(gallery)
        tech.save(update_fields=["gallery"])
        messages.success(request, "Image deleted.")
    else:
        messages.error(request, "Image not found.")

    return _redirect_back_to_edit(request, pk)


#---------------------------------------------------------------------------------------------Mindmap-------------------------------------------------------------------------------------------------------------


def mindmap_view(request):
    cursor = technologies.find({},{"_id": 0, "name": 1, "macro": 1, "meso1": 1, "meso2": 1},)

    macro_map = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in cursor:
        name  = (r.get("name")  or "").strip() or "Unnamed Technology"
        macro = (r.get("macro") or "").strip() or "Uncategorized"
        meso1 = (r.get("meso1") or "").strip()
        meso2 = (r.get("meso2") or "").strip()

        if meso1 and meso2:
            macro_map[macro][meso1][meso2].append(name)
        elif meso1:
            macro_map[macro][meso1][""].append(name)
        else:
            macro_map[macro]["Uncategorized"][""].append(name)

    children = []
    for macro, meso1_dict in macro_map.items():
        macro_node = {"topic": macro, "children": []}
        for meso1, meso2_dict in meso1_dict.items():
            if any(k for k in meso2_dict if k):
                meso1_node = {"topic": meso1, "children": []}
                for meso2, techs in meso2_dict.items():
                    if meso2:
                        meso1_node["children"].append(
                            {"topic": meso2, "children": [{"topic": t} for t in techs]}
                        )
                    else:
                        meso1_node["children"].extend([{"topic": t} for t in techs])
                macro_node["children"].append(meso1_node)
            else:
                for _, techs in meso2_dict.items():
                    macro_node["children"].append(
                        {"topic": meso1, "children": [{"topic": t} for t in techs]}
                    )
        children.append(macro_node)

    mindmap_data = {
        "nodeData": {"id": "root", "topic": "  Disruptive\nTechnologies", "children": children},
        "direction": 0, "arrows": [], "summaries": [],
        "theme": {
            "name": "Latte", "type": "light",
            "palette": ["#dd7878","#ea76cb","#8839ef","#e64553","#fe640b",
                        "#df8e1d","#40a02b","#209fb5","#1e66f5","#7287fd"],
            "cssVar": {"--gap":"30px","--main-color":"#444446","--main-bgcolor":"#ffffff",
                       "--color":"#777777","--bgcolor":"#f6f6f6","--panel-color":"#444446",
                       "--panel-bgcolor":"#ffffff","--panel-border-color":"#eaeaea"},
        },
    }
    return render(request, "Mindmap/mindmap.html",
                  {"mindmap_json": json.dumps(mindmap_data, ensure_ascii=False)})





# ---------------------------------------------------------------------------------------------Evaluation form + charts ---------------------------------------------------------------------------------------------------------------------------


def _load_eval_history(tech):
    try:
        # uses your model's JSON helpers
        return Technology._loads(tech.evaluation_history, [])
    except Exception:
        return []

def _save_eval_history(tech, items):
    tech.evaluation_history = Technology._dumps(items)
    tech.save(update_fields=["evaluation_history", "last_modified"])




CONFIDENCE_LEVELS = ["Low", "Modest", "Moderate", "High"]
CONFIDENCE_MAP = {"Low": 1, "Modest": 3, "Moderate": 5, "High": 9}

def project_positioning(scores, amplification_factor):
    A = amplification_factor
    diag = A / (A + 7)
    off_diag = (1 - diag) / 7
    mat = np.full((8, 8), off_diag)
    np.fill_diagonal(mat, diag)
    scores = np.array(scores)
    result = mat * scores[:, None]
    column_sums = result.sum(axis=0)
    return {
        "bar": np.round(column_sums, 4).tolist(),
        "bar_min": float(np.round(column_sums.min(), 4)),
        "bar_max": float(np.round(column_sums.max(), 4)),
    }

@require_action("evaluate_technology")
def evaluate(request, pk):
    technology = get_object_or_404(Technology, pk=pk)

    radar1_labels_full = [
        "Benefits for Safran image & strategy",
        "Level of differentiation VS. market / competitors",
        "Sustainability of the differentiation / Barriers to entry",
        "Addressable market for Safran (qualitative scale)",
        "Market robustness (stability regarding external events)",
        "Economic value creation (qualitative scale)",
        "Group transversality level",
        "Other value creation",
    ]
    radar2_labels_full = [
        "Maturity of the critical technologies needed",
        "Technical competences accessibility",
        "Industrial feasibility",
        "Business Readiness Level",
        "Marketability / Commercialization feasibility",
        "Level of investments Demonstration Non Recurring Costs",
        "Funding",
        "Other major risk(s)",
    ]
    radar1_short = [
        "Strategy and image","Differentiation","Barriers to entry","Addressable market (revenue)",
        "Market robustness","Economic value creation","Group versetality","Other value creation"
    ]
    radar2_short = [
        "Critical technos maturity","Competences accessibility","Industrial feasibility","Business readiness level",
        "Commercialization feasibility","Investments (demo NRC)","Funding","Other major risk(s)"
    ]
    score_options = [1, 3, 5, 9]
    confidence_levels = CONFIDENCE_LEVELS

    # ---- Load last saved snapshot (if any) ----
    hist = _load_eval_history(technology)
    last = hist[-1] if hist else None

    default_values = [1]*16
    default_confidences = ["Moderate"]*16
    default_ampl = 2.0
    default_comments = [""]*16

    prefill_values = (last or {}).get("values", default_values)
    prefill_confidences = (last or {}).get("confidences", default_confidences)
    prefill_comments = (last or {}).get("comments", default_comments)
    try:
        prefill_amplification = float((last or {}).get("amplification", default_ampl))
    except (TypeError, ValueError):
        prefill_amplification = default_ampl

    # Seed session so Export works (regardless of save)
    request.session["user_values"] = prefill_values
    request.session["user_confidences"] = prefill_confidences
    request.session["user_comments"] = prefill_comments 
    request.session["amplification"] = prefill_amplification

    # Build base context (prefilled)
    context = {
        "technology": technology,
        "tech_id": technology.pk,
        "radar1": radar1_labels_full,
        "radar2": radar2_labels_full,
        "radar1_short": radar1_short,
        "radar2_short": radar2_short,
        "score_options": score_options,
        "confidence_levels": confidence_levels,
        "show_chart": False,
        "radar2_indexes": list(range(len(radar1_short), len(radar1_short) + len(radar2_short))),
        "user_values": prefill_values,
        "user_confidences": prefill_confidences,
        "user_comments": prefill_comments,  
        "amplification": prefill_amplification,
    }

    # If we have a saved snapshot, show its metadata and charts on GET
    if request.method != "POST" and last:
        # Metadata for header
        saved_user = (last.get("user") or "Unknown")
        saved_ts = last.get("timestamp")
        try:
            # Format to "dd.MM.yyyy HH:mm"
            dt = timezone.datetime.fromisoformat(saved_ts) if saved_ts else None
            dt = timezone.make_aware(dt) if dt and timezone.is_naive(dt) else dt
            dt_local = timezone.localtime(dt) if dt else None
            when_str = dt_local.strftime("%d.%m.%Y %H:%M") if dt_local else ""
        except Exception:
            when_str = saved_ts or ""

        context["eval_meta"] = {"user": saved_user, "when": when_str}

        # Compute charts from saved values
        values = prefill_values
        confidences = prefill_confidences
        amplification = prefill_amplification

        context["user_comments"] = prefill_comments


        r1n, r2n = len(radar1_short), len(radar2_short)
        radar1_values = values[:r1n]
        radar2_values = values[r1n:r1n+r2n]

        stake_scores = radar1_values + [1]*(8-len(radar1_values))
        feas_scores  = radar2_values + [1]*(8-len(radar2_values))

        stake_bar_info = project_positioning(stake_scores, amplification)
        feas_bar_info  = project_positioning(feas_scores,  amplification)

        conf_scores = [CONFIDENCE_MAP.get(c, 1) for c in confidences]
        stake_conf_bar_info = project_positioning(conf_scores[:8],  amplification)
        feas_conf_bar_info  = project_positioning(conf_scores[8:16], amplification)

        def get_qualification_statement(parameter: str, value: int) -> str:
            """
            Fetch qualification statement for a given parameter + value (1,3,5,9).
            """
            doc = qualifications.find_one({"parameter": parameter}, {"statements": 1})
            if not doc:
                return "—"
            stmts = doc.get("statements", {})
            return stmts.get(str(value), "—")

        all_labels_full = radar1_labels_full + radar2_labels_full
        qualification_statements = [
            (param, values[i], get_qualification_statement(param, values[i]),
            confidences[i] if i < len(confidences) else "")
            for i, param in enumerate(all_labels_full)
            if i < len(values)
        ]

        context.update({
            "show_chart": True,
            "radar1_values": radar1_values,
            "radar2_values": radar2_values,
            "qualification_statements": qualification_statements,
            "amplification": amplification,
            "stake_bar": stake_bar_info["bar"], "stake_bar_min": stake_bar_info["bar_min"], "stake_bar_max": stake_bar_info["bar_max"],
            "feas_bar":  feas_bar_info["bar"],  "feas_bar_min":  feas_bar_info["bar_min"],  "feas_bar_max":  feas_bar_info["bar_max"],
            "stake_conf_bar": stake_conf_bar_info["bar"], "stake_conf_bar_min": stake_conf_bar_info["bar_min"], "stake_conf_bar_max": stake_conf_bar_info["bar_max"],
            "feas_conf_bar":  feas_conf_bar_info["bar"],  "feas_conf_bar_min":  feas_conf_bar_info["bar_min"],  "feas_conf_bar_max":  feas_conf_bar_info["bar_max"],
        })

    if request.method == "POST":
        action = request.POST.get("action")  # "preview" or "save"

        values = [int(v) for v in request.POST.getlist("values[]")]
        confidences = request.POST.getlist("confidences[]")
        raw_comments = request.POST.getlist("comments[]")
        comments = [ (raw_comments[i].strip() if i < len(raw_comments) else "") for i in range(16) ]
        try:
            amplification = float(request.POST.get("amplification", 2))
        except (TypeError, ValueError):
            amplification = 2.0

        # Always update session for export
        request.session["user_values"] = values
        request.session["user_confidences"] = confidences
        request.session["user_comments"] = comments     
        request.session["amplification"] = amplification

        # If action == "save": persist snapshot with timestamp+user
        if action == "save":
            eval_data = {
                "values": values,
                "confidences": confidences,
                "comments": comments,
                "amplification": amplification,
                "timestamp": timezone.now().isoformat(),
                "user": (request.user.username if getattr(request, "user", None)
                         and request.user.is_authenticated else "Anonymous"),
                "version": 1,
            }
            _save_eval_history(technology, [eval_data])  # keep only latest; use hist+append to keep history

            log_activity(
                username=request.user.get_username() if request.user.is_authenticated else "Anonymous",
                activity="Evaluate technology",        # <= used to filter later
                logged_in=bool(request.user.is_authenticated),
                meta={"technology_id": str(technology.pk), "technology_name": technology.name},
            )


            # Pass meta to the template
            dt_local = timezone.localtime(timezone.now())
            context["eval_meta"] = {
                "user": eval_data["user"],
                "when": dt_local.strftime("%d.%m.%Y %H:%M"),
            }

        # Compute charts for the current POST (preview or saved)
        r1n, r2n = len(radar1_short), len(radar2_short)
        radar1_values = values[:r1n]
        radar2_values = values[r1n:r1n+r2n]

        stake_scores = radar1_values + [1]*(8-len(radar1_values))
        feas_scores  = radar2_values + [1]*(8-len(radar2_values))

        stake_bar_info = project_positioning(stake_scores, amplification)
        feas_bar_info  = project_positioning(feas_scores,  amplification)

        conf_scores = [CONFIDENCE_MAP.get(c, 1) for c in confidences]
        stake_conf_bar_info = project_positioning(conf_scores[:8],  amplification)
        feas_conf_bar_info  = project_positioning(conf_scores[8:16], amplification)


        def get_qualification_statement(parameter: str, value: int) -> str:
            """
            Fetch qualification statement for a given parameter + value (1,3,5,9).
            """
            doc = qualifications.find_one({"parameter": parameter}, {"statements": 1})
            if not doc:
                return "—"
            stmts = doc.get("statements", {})
            return stmts.get(str(value), "—")

        all_labels_full = radar1_labels_full + radar2_labels_full
        qualification_statements = [
            (param, values[i], get_qualification_statement(param, values[i]),
            confidences[i] if i < len(confidences) else "")
            for i, param in enumerate(all_labels_full)
            if i < len(values)
        ]


        context.update({
            "show_chart": True,
            "radar1_values": radar1_values,
            "radar2_values": radar2_values,
            "qualification_statements": qualification_statements,
            "amplification": amplification,
            "stake_bar": stake_bar_info["bar"], "stake_bar_min": stake_bar_info["bar_min"], "stake_bar_max": stake_bar_info["bar_max"],
            "feas_bar":  feas_bar_info["bar"],  "feas_bar_min":  feas_bar_info["bar_min"],  "feas_bar_max":  feas_bar_info["bar_max"],
            "stake_conf_bar": stake_conf_bar_info["bar"], "stake_conf_bar_min": stake_conf_bar_info["bar_min"], "stake_conf_bar_max": stake_conf_bar_info["bar_max"],
            "feas_conf_bar":  feas_conf_bar_info["bar"],  "feas_conf_bar_min":  feas_conf_bar_info["bar_min"],  "feas_conf_bar_max":  feas_conf_bar_info["bar_max"],
            "user_values": values,
            "user_confidences": confidences,
            "user_comments": comments, 
        })

    return render(request, "Evaluation/evaluation_form.html", context)



# ------------------------ Save chart image to Technology.gallery (B64) ---------------------------

@csrf_exempt
@require_action("evaluate_technology")
def save_chart_image(request, pk):
    if request.method != 'POST':
        return JsonResponse({'status': 'fail'}, status=400)

    tech = get_object_or_404(Technology, pk=pk)

    try:
        data = json.loads(request.body or "{}")
        # Your JS sends raw base64 (no prefix), so we reattach the data URL header:
        raw_b64 = data.get("image_base64")
        if not raw_b64:
            return JsonResponse({'status': 'fail', 'error': 'No image provided'}, status=400)
        data_url = f"data:image/png;base64,{raw_b64}"
    except Exception as e:
        return JsonResponse({'status': 'fail', 'error': str(e)}, status=400)

    # Build new gallery entry (inline base64, no file storage)
    entry = {
        "name": data.get("name", f"eval_{pk}.png"),
        "b64": data_url,                   # <-- inline base64 for <img src="{{ item.b64 }}">
        "tag": "",                      # keep your tag scheme
        "type": "evaluation",              # used to identify/replace old one
        "uploaded_at": datetime.now().isoformat(),
    }

    # Replace any previous evaluation image
    gallery = tech.gallery_list
    if not isinstance(gallery, list):
        gallery = []

    # drop prior entries whose type is 'evaluation'
    gallery = [g for g in gallery if (g or {}).get("type") != "evaluation"]
    gallery.append(entry)

    tech.set_gallery(gallery)
    tech.save(update_fields=["gallery", "last_modified"])

    return JsonResponse({'status': 'success'})

#--------------------------------------------------------Export to excel------------------------------------------------------------
# apps/technology/views.py  (only the relevant parts)

# apps/technology/views.py  (only the relevant parts)

import os, re, shutil, tempfile, zipfile
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

# ✅ CORRECT import for the .NET wheel you installed: aspose-cells-python
from aspose.cells import Workbook

# from .models import Technology
# from .decorators import require_action
# from .constants import CONFIDENCE_MAP   # wherever you define it

def _safe_filename(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", (s or "")).strip().replace("  ", " ")

def _detect_output_ext(template_path: str) -> str:
    """Return '.xlsm' if template is macro-enabled, else '.xlsx'."""
    try:
        with zipfile.ZipFile(template_path, "r") as z:
            names = {n.lower() for n in z.namelist()}
            if "xl/vbaproject.bin" in names:
                return ".xlsm"
            ct = z.read("[Content_Types].xml").decode("utf-8", "ignore").lower()
            if "macroenabled" in ct:
                return ".xlsm"
    except Exception:
        pass
    return ".xlsx"

def _numish(x):
    if isinstance(x, (int, float)) or x is None:
        return x
    s = str(x).strip().replace(",", ".")
    try:
        return float(s)
    except Exception:
        return x

@require_action("evaluate_technology")
def export_excel(request, pk):
    tech = get_object_or_404(Technology, pk=pk)
    tech_name = tech.name or "Technology"
    safe_name = _safe_filename(tech_name)

    values = request.session.get("user_values")
    confidences = request.session.get("user_confidences")
    comments = request.session.get("user_comments") or [""] * 16

    try:
        amplification = float(request.session.get("amplification", 2))
    except (TypeError, ValueError):
        amplification = 2.0

    if not values or not confidences:
        return HttpResponse("No evaluation data found.", status=400)

    # point to your template (xlsx or xlsm)
    template_path = os.path.join(
        str(settings.BASE_DIR), "apps", "templates", "Evaluation", "evaluation_template.xlsx"
    )
    if not os.path.exists(template_path):
        return HttpResponse("Template file not found", status=404)

    # copy to a temp file we'll modify and stream back
    tmp_dir = tempfile.mkdtemp()
    ext = _detect_output_ext(template_path)  # keep .xlsm if macro-enabled
    out_name = f"{safe_name} evaluation result{ext}"
    export_path = os.path.join(tmp_dir, out_name)
    shutil.copy(template_path, export_path)

    # ✅ Open with Aspose.Cells (.NET) – no JVM / JPype needed
    wb = Workbook(export_path)

    # get sheet (adjust name if different)
    try:
        ws = wb.worksheets.get("iS0 evaluation")
        if ws is None:
            ws = wb.worksheets[0]
    except Exception:
        ws = wb.worksheets[0]

    cells = ws.cells

    confidence_map = CONFIDENCE_MAP
    if len(comments) < 16:
        comments += [""] * (16 - len(comments))

    # write values exactly like your COM version
    for i in range(16):
        row = 6 + i * 2
        cells.get(f"F{row}").put_value(_numish(values[i]))
        cells.get(f"J{row}").put_value(f"{confidences[i]} level of confidence in the evaluation")
        cells.get(f"K{row}").put_value(_numish(confidence_map.get(confidences[i], 1)))
        cells.get(f"L{row}").put_value(comments[i])

    cells.get("F39").put_value(_numish(amplification))
    cells.get("L2").put_value(tech_name)

    # recalc formulas so charts are up-to-date in the file
    wb.calculate_formula()
    wb.save(export_path)

    # stream to browser
    with open(export_path, "rb") as f:
        data = f.read()

    content_type = (
        "application/vnd.ms-excel.sheet.macroEnabled.12"
        if out_name.lower().endswith(".xlsm")
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp = HttpResponse(data, content_type=content_type)
    resp["Content-Disposition"] = (
        f'attachment; filename="{out_name}"; filename*=UTF-8\'\'{quote(out_name)}'
    )
    return resp




#---------------------------------------------------------------------------------------Scorecard-------------------------------------------------------------------------------------------------------------------------------

xframe_options_sameorigin
@require_action("scorecard_generate")
def generate_report(request, pk):
    t = get_object_or_404(Technology, pk=pk)

    # Gallery: list of dicts with keys like {name, b64, tag, type, uploaded_at}
    gallery = t.gallery_list if isinstance(t.gallery_list, list) else []
    sc1 = next((g for g in gallery if (g or {}).get("tag") == "SC1"), None)
    sc2 = next((g for g in gallery if (g or {}).get("tag") == "SC2"), None)

    evals = [g for g in gallery if (g or {}).get("type") == "evaluation"]
    def _uploaded_at(g):
        try:
            return datetime.fromisoformat((g or {}).get("uploaded_at","").replace("Z","+00:00"))
        except Exception:
            return datetime.min
    evaluation_img = sorted(evals, key=_uploaded_at, reverse=True)[0] if evals else None

    context = {
        "technology": {
            "Name": t.name,
            "Macro": t.macro,
            "Meso1": t.meso1,
            "Meso2": t.meso2,
            "Meso": "",  # your template checks this, keep empty if not used
            "confidentiality": t.confidentiality,
            "initial_date": t.initial_date,
            "last_modified": t.last_modified,
            # Map your model fields to the template’s expected keys
            "Fields": {
                "description_application": mark_safe(t.desc_and_applications or ""),
                "publications_projects":   mark_safe(t.publications_and_projects or ""),
                "attributes_performance":  mark_safe(t.attributes_and_performance or ""),
                "strategic_value":         mark_safe(t.strategic_value_and_evaluation or ""),
                "challenges_status":       mark_safe(t.challenges_and_current_status or ""),
                "enabling_tech":           mark_safe(t.enabling_technologies or ""),
            },
        },
        "generated_on": localtime(make_aware(datetime.now())),
        "sc1": sc1,                 # use sc1.b64 in template
        "sc2": sc2,                 # use sc2.b64
        "evaluation_img": evaluation_img,  # use evaluation_img.b64
    }
    return render(request, "Scorecard/Scorecard.html", context) 


# ------------------------------------------Compendium-----------------------------------------------------------
from datetime import datetime
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.utils.timezone import make_aware, localtime

from .models import Technology

def _gallery_list(doc):
    """Return gallery as a Python list (handles list or JSON string)."""
    g = doc.get("gallery", "[]")
    if isinstance(g, list):
        return g
    try:
        return json.loads(g or "[]")
    except Exception:
        return []

def _latest_eval(gallery):
    evals = [x for x in gallery if (x or {}).get("type") == "evaluation"]
    def key(x):
        try:
            return datetime.fromisoformat((x or {}).get("uploaded_at", "").replace("Z", "+00:00"))
        except Exception:
            return datetime.min
    return sorted(evals, key=key, reverse=True)[0] if evals else None

@require_GET
def api_techs(request):
    """
    Return minimal fields for the selector modal in a normalized, robust shape.
    Output item keys: id (str), name, macro, meso1, meso2, status
    """
    include_inactive = request.GET.get("inactive") == "1"
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        return JsonResponse({"ok": False, "error": "MongoDB not reachable"}, status=503)

    # Pull both 'id' and '_id' so we can normalize either.
    query = {} if include_inactive else {"$or": [{"status": {"$ne": "inactive"}}, {"is_active": True}]}
    proj = {
        "_id": 1, "id": 1, "name": 1,
        "macro": 1, "meso1": 1, "meso2": 1,
        "is_active": 1, "status": 1
    }
    raw = list(technologies.find(query, proj))

    def _norm_id(d):
        if "id" in d and d["id"] not in (None, ""):
            return str(d["id"])
        _id = d.get("_id")
        # ObjectId → hex string; else just str()
        return str(_id) if _id is not None else None

    def _norm_status(d):
        s = (d.get("status") or "").strip().lower()
        if s in {"active", "inactive", "dormant"}:
            return s
        ia = d.get("is_active", None)
        if ia is True or (isinstance(ia, str) and ia.lower() in {"1","true","t","yes","y"}):
            return "active"
        if ia is False or (isinstance(ia, str) and ia.lower() in {"0","false","f","no","n"}):
            return "inactive"
        # default to active if truly missing (matches your earlier behavior)
        return "active"

    items = []
    for d in raw:
        _id = _norm_id(d)
        name = (d.get("name") or "").strip()
        if not _id or not name:
            continue
        items.append({
            "id": _id,
            "name": name,
            "macro": (d.get("macro") or "").strip(),
            "meso1": (d.get("meso1") or "").strip(),
            "meso2": (d.get("meso2") or "").strip(),
            "status": _norm_status(d),
        })

    items.sort(key=lambda x: x["name"].lower())
    return JsonResponse({"ok": True, "items": items})

def _scorecard_context_from_doc(doc: dict) -> dict:
    """Map a Mongo document to the context your Scorecard template expects."""
    gallery = _gallery_list(doc)
    sc1 = next((x for x in gallery if (x or {}).get("tag") == "SC1"), None)
    sc2 = next((x for x in gallery if (x or {}).get("tag") == "SC2"), None)
    evaluation_img = _latest_eval(gallery)

    # Map DB fields -> template keys (matches your Django model names)
    ctx = {
        "technology": {
            "Name": doc.get("name", ""),
            "Macro": doc.get("macro", ""),
            "Meso1": doc.get("meso1", ""),
            "Meso2": doc.get("meso2", ""),
            "Meso": "",
            "confidentiality": doc.get("confidentiality", "C2"),
            "initial_date": doc.get("initial_date"),
            "last_modified": doc.get("last_modified"),
            "Fields": {
                "description_application": mark_safe(doc.get("desc_and_applications", "") or ""),
                "publications_projects":   mark_safe(doc.get("publications_and_projects", "") or ""),
                "attributes_performance":  mark_safe(doc.get("attributes_and_performance", "") or ""),
                "strategic_value":         mark_safe(doc.get("strategic_value_and_evaluation", "") or ""),
                "challenges_status":       mark_safe(doc.get("challenges_and_current_status", "") or ""),
                "enabling_tech":           mark_safe(doc.get("enabling_technologies", "") or ""),
            },
        },
        "generated_on": localtime(make_aware(datetime.now())),
        "sc1": sc1,                  # use .b64 in template
        "sc2": sc2,                  # use .b64 in template
        "evaluation_img": evaluation_img,  # use .b64 in template
        "compendium_mode": True,     # enables print CSS in your scorecard template if you added it
    }
    return ctx


@require_http_methods(["GET", "POST"])
def scorecard_selector(request):

    if request.method == "GET":
        include_inactive = request.GET.get("inactive") == "1"
        query = {} if include_inactive else {"is_active": True}
        # ⬇️ fetch macro/meso fields for filtering
        cursor = technologies.find(query, {
            "_id": 0, "id": 1, "name": 1, "macro": 1, "meso1": 1, "meso2": 1, "is_active": 1
        })
        techs = list(cursor)
        techs.sort(key=lambda d: (d.get("name") or "").lower())

        # Build distinct, sorted filter options
        def _opts(key):
            vals = { (d.get(key) or "").strip() for d in techs if d.get(key) }
            return sorted(vals, key=str.lower)

        macro_opts = _opts("macro")
        meso1_opts = _opts("meso1")
        meso2_opts = _opts("meso2")

        return render(request, "Scorecard/Selector.html", {
            "techs": techs,
            "include_inactive": include_inactive,
            "macro_opts": macro_opts,
            "meso1_opts": meso1_opts,
            "meso2_opts": meso2_opts,
        })

    # POST (unchanged)
    ids = request.POST.getlist("order[]") or request.POST.getlist("order")
    if not ids:
        # re-render with defaults if no selection
        cursor = technologies.find({"is_active": True},
                                   {"_id": 0, "id": 1, "name": 1, "macro": 1, "meso1": 1, "meso2": 1, "is_active": 1})
        techs = sorted(list(cursor), key=lambda d: (d.get("name") or "").lower())
        def _opts(key):
            vals = { (d.get(key) or "").strip() for d in techs if d.get(key) }
            return sorted(vals, key=str.lower)
        return render(request, "Scorecard/Selector.html", {
            "techs": techs,
            "error": "Please select at least one item.",
            "macro_opts": _opts("macro"),
            "meso1_opts": _opts("meso1"),
            "meso2_opts": _opts("meso2"),
        })

    request.session["scorecard_order_ids"] = ids
    return render(request, "Scorecard/ForwardToBuild.html", {})


def scorecard_compendium(request):
    # ids from session or POST
    ids = request.session.pop("scorecard_order_ids", None) or request.POST.getlist("order[]") or []
    if not ids:
        cursor = technologies.find({"is_active": True}, {"_id": 0, "id": 1, "name": 1, "macro": 1})
        techs = sorted(list(cursor), key=lambda d: (d.get("name") or "").lower())
        return render(request, "Scorecard/Selector.html", {"techs": techs, "error": "No selection received."})

    # fetch docs by integer id, preserve order
    docs = []
    for sid in ids:
        try:
            doc = technologies.find_one({"id": int(sid)})
        except ValueError:
            doc = None
        if doc:
            docs.append(doc)

    # stitch pages with your existing Scorecard/Scorecard.html
    pages_html = [render_to_string("Scorecard/Scorecard.html", _scorecard_context_from_doc(d)) for d in docs]
    combined_html = "\n".join(pages_html)

    return render(request, "Scorecard/Compendium.html", {
        "compendium_mode": True, 
        "combined_html": combined_html,
        "filename": f"scorecards_{localtime(make_aware(datetime.now())).strftime('%Y%m%d')}.pdf"
    })


#-----------------------------Notes--------------------------------------------------
 

def _safe_sort_key(n):
    v = n.get("created_at")
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.timestamp()
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("T", " "))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            return 0
    return 0


def _render_notes_fragment(request, pk: int):
    doc = technologies.find_one({"id": pk}, {"notes": 1, "_id": 0}) or {}
    notes = doc.get("notes", [])

    # sort while values may still be datetime/ISO
    notes.sort(key=_safe_sort_key, reverse=True)

    for n in notes:
        if "_id" in n and n["_id"] is not None:
            n["note_id"] = str(n["_id"])
            n.pop("_id", None)

        dt = n.get("created_at")

        # normalize to aware UTC
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        elif isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace("T", " "))
            except Exception:
                dt = None
            if isinstance(dt, datetime) and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

        # convert to Europe/Berlin for display
        if isinstance(dt, datetime):
            local_dt = dt.astimezone(BERLIN)   # handles CET/CEST automatically
            n["created_at"] = local_dt.strftime("%Y-%m-%d %H:%M")
        else:
            n["created_at"] = n.get("created_at") or ""

    return render(request, "technology/_notes.html", {"tech_id": pk, "notes": notes})


@login_required
@require_http_methods(["GET"])
def tech_notes(request, pk: int):
    return _render_notes_fragment(request, pk)   # <-- return!

@login_required
@require_http_methods(["POST"])
def tech_notes_add(request, pk: int):
    text = (request.POST.get("text") or "").strip()
    if not text:
        return HttpResponseBadRequest("Empty")

    note = {
        "_id": ObjectId(),
        "author_id": request.user.id,
        "author_name": (getattr(request.user, "get_full_name", lambda: "")() or request.user.username),
        "text": text[:300],
        "created_at": datetime.now(timezone.utc),
    }
    technologies.update_one({"id": pk}, {"$push": {"notes": note}})
    return _render_notes_fragment(request, pk)   # <-- return!

@login_required
@require_http_methods(["POST"])
def tech_notes_delete(request, pk: int, note_id: str):
    try:
        note_oid = ObjectId(note_id)
    except Exception:
        return HttpResponseBadRequest("Bad note id")

    technologies.update_one(
        {"id": pk},
        {"$pull": {"notes": {"_id": note_oid, "author_id": request.user.id}}},
    )
    return _render_notes_fragment(request, pk)   # <-- return!
