# apps/technology/views.py
import csv
import json
import datetime
import base64
import imghdr

from apps.common.activity_log import log_activity

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

#(Excel COM)
import pythoncom, win32com.client as win32


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



#-------------Pymongo defined--------------------------

client = MongoClient("mongodb://localhost:27017/")
db = client["tech_tool_db"]
technologies = db["technology_technology"] 


# -------------------------- small helpers --------------------------

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

def _parse_active(request):
    raw = {(v or "").strip().lower() for v in request.GET.getlist("active")}
    has_true = bool(raw & _TRUTHY)
    has_false = bool(raw & _FALSY)
    if has_true and not has_false:
        return True, {"1"}
    if has_false and not has_true:
        return False, {"0"}
    sel = set()
    if has_true: sel.add("1")
    if has_false: sel.add("0")
    return None, sel

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

def apply_filters_and_sort(request, qs):
    # Search
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(macro__icontains=q) |
            Q(meso1__icontains=q) |
            Q(meso2__icontains=q) |
            Q(description__icontains=q)
        )

    # Category filter (matches any of macro/meso1/meso2)
    selected_categories = [c.strip() for c in request.GET.getlist("categories") if c.strip()]
    if selected_categories:
        qcat = Q()
        for c in selected_categories:
            qcat |= Q(macro__iexact=c) | Q(meso1__iexact=c) | Q(meso2__iexact=c)
        qs = qs.filter(qcat)

    # Active filter — Djongo-safe style
    active_filter, _ = _parse_active(request)
    if active_filter is True:
        qs = qs.filter(is_active__in=[True])
    elif active_filter is False:
        qs = qs.filter(is_active__in=[False])

    # Sort
    sort = (request.GET.get("sort") or "created_desc").strip()
    if sort in ("active_asc", "active_desc"):
        try:
            qs = qs.annotate(_active_i=Case(
                When(is_active=True, then=1),
                default=0,
                output_field=IntegerField(),
            )).order_by("-_active_i" if sort == "active_desc" else "_active_i", "-created_at")
        except DatabaseError:
            qs = qs.order_by("-created_at")
    else:
        ordering_map = {
            "name_asc": "name",
            "name_desc": "-name",
            "created_asc": "created_at",
            "created_desc": "-created_at",
        }
        qs = qs.order_by(ordering_map.get(sort, "-created_at"))

    return qs


# -------------------------- list / details --------------------------

class TechnologyListView(LoginRequiredMixin, ListView):
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
        _, active_selected = _parse_active(self.request)
        ctx["active_selected"] = active_selected
        ctx["sort"] = (self.request.GET.get("sort") or "created_desc").strip()
        return ctx


class TechnologyDetailView(LoginRequiredMixin, DetailView):
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
    model = Technology
    form_class = TechnologyForm
    template_name = "technology/create.html"
    success_url = reverse_lazy("technology_list")



class TechnologyUpdateView(LoginRequiredMixin, UpdateView):
    model = Technology
    form_class = TechnologyForm
    template_name = "technology/create.html"  # reuse same page
    pk_url_kwarg = "pk"
    context_object_name = "object"

    def form_valid(self, form):
        try:
            resp = super().form_valid(form)
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


# -------------------------- taxonomy JSON APIs --------------------------

@require_GET
def api_macros(request):
    rows = (Technology.objects
            .exclude(macro="")
            .values_list("macro", flat=True)
            .distinct().order_by("macro"))
    return JsonResponse([{"name": m} for m in rows], safe=False)

@require_GET
def api_meso1(request, macro):
    rows = (Technology.objects
            .filter(macro=macro)
            .exclude(meso1="")
            .values_list("meso1", flat=True)
            .distinct().order_by("meso1"))
    return JsonResponse([{"name": m} for m in rows], safe=False)

@require_GET
def api_meso2(request, meso1):
    rows = (Technology.objects
            .filter(meso1=meso1)
            .exclude(meso2="")
            .values_list("meso2", flat=True)
            .distinct().order_by("meso2"))
    return JsonResponse([{"name": m} for m in rows], safe=False)


# -------------------------- CSV export --------------------------

class TechnologyCompendiumView(LoginRequiredMixin, View):
    def get(self, request):
        qs = apply_filters_and_sort(request, Technology.objects.all())
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="technology_compendium.csv"'
        w = csv.writer(resp)
        w.writerow(["ID", "Name", "Macro", "Meso1", "Meso2", "Active", "Created", "Confidentiality"])
        for t in qs:
            w.writerow([
                t.pk,
                t.name,
                t.macro or "",
                t.meso1 or "",
                t.meso2 or "",
                "Yes" if t.is_active else "No",
                t.created_at.strftime("%Y-%m-%d %H:%M"),
                t.confidentiality,
            ])

        return resp


# -------------------------- Extra fields (add/edit/delete) --------------------------

@require_POST
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


#-----------------------Mindmap-----------------------------------------------------

from pymongo import MongoClient


MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB  = "tech_tool_db"                 # or whatever DB you actually use now
TECH_COLLECTION_NAME = "technology_technology"  # Django's default table/collection name


client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

technologies = db[TECH_COLLECTION_NAME]


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
        "nodeData": {"id": "root", "topic": "Technologies", "children": children},
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





# -------------------------------------------------------Evaluation form + charts ---------------------------------------------------


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
        "Demo.NRC",
        "Funding",
    ]
    radar1_short = [
        "Strategy and image","Differentiation","Barriers to entry","Addressable market (revenue)",
        "Market robustness","Economic value creation","Group versetality","Other value creation"
    ]
    radar2_short = [
        "Critical technos maturity","Competences accessibility","Industrial feasibility","Business readiness level",
        "Commercialization feasibility","Investments (demo NRC)","Demo.NRC","Funding"
    ]
    score_options = [1, 3, 5, 9]
    confidence_levels = CONFIDENCE_LEVELS

    # ---- Load last saved snapshot (if any) ----
    hist = _load_eval_history(technology)
    last = hist[-1] if hist else None

    default_values = [1]*16
    default_confidences = ["Moderate"]*16
    default_ampl = 2.0

    prefill_values = (last or {}).get("values", default_values)
    prefill_confidences = (last or {}).get("confidences", default_confidences)
    try:
        prefill_amplification = float((last or {}).get("amplification", default_ampl))
    except (TypeError, ValueError):
        prefill_amplification = default_ampl

    # Seed session so Export works (regardless of save)
    request.session["user_values"] = prefill_values
    request.session["user_confidences"] = prefill_confidences
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

        def get_statement(param, val): return f"Qualification statement for {param} at {val}"
        qualification_statements = [
            (param, values[i], get_statement(param, values[i]),
             confidences[i] if i < len(confidences) else "")
            for i, param in enumerate(radar1_labels_full + radar2_labels_full)
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
        try:
            amplification = float(request.POST.get("amplification", 2))
        except (TypeError, ValueError):
            amplification = 2.0

        # Always update session for export
        request.session["user_values"] = values
        request.session["user_confidences"] = confidences
        request.session["amplification"] = amplification

        # If action == "save": persist snapshot with timestamp+user
        if action == "save":
            eval_data = {
                "values": values,
                "confidences": confidences,
                "amplification": amplification,
                "timestamp": timezone.now().isoformat(),
                "user": (request.user.username if getattr(request, "user", None)
                         and request.user.is_authenticated else "Anonymous"),
                "version": 1,
            }
            _save_eval_history(technology, [eval_data])  # keep only latest; use hist+append to keep history

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

        def get_statement(param, val): return f"Qualification statement for {param} at {val}"
        qualification_statements = [
            (param, values[i], get_statement(param, values[i]),
             confidences[i] if i < len(confidences) else "")
            for i, param in enumerate(radar1_labels_full + radar2_labels_full)
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
        })

    return render(request, "Evaluation/evaluation_form.html", context)




# ------------------------ Save chart image to Technology.gallery (B64) ---------------------------

@csrf_exempt
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


# ----- Excel export (uses session values) -----

def _safe_filename(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", (s or "")).strip().replace("  ", " ")


def export_excel(request, pk):

    tech = get_object_or_404(Technology, pk=pk)
    tech_name = tech.name or "Technology"
    safe_name = _safe_filename(tech_name)

    values = request.session.get("user_values")
    confidences = request.session.get("user_confidences")
    try:
        amplification = float(request.session.get("amplification", 2))
    except (TypeError, ValueError):
        amplification = 2.0

    if not values or not confidences:
        return HttpResponse("No evaluation data found.", status=400)

    template_path = os.path.join(settings.BASE_DIR / "apps" / "templates" / "Evaluation" / "evaluation_template.xlsx")
    if not os.path.exists(template_path):
        return HttpResponse("Template file not found", status=404)

    pythoncom.CoInitialize()

    tmp_dir = tempfile.mkdtemp()
    export_path = os.path.join(tmp_dir, f"{safe_name} Evaluation result.xlsx")
    shutil.copy(template_path, export_path)

    excel = win32.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    wb = excel.Workbooks.Open(os.path.abspath(export_path))
    ws = wb.Worksheets("iS0 evaluation")

    confidence_map = CONFIDENCE_MAP

    for i in range(16):
        row = 6 + i * 2
        ws.Range(f"F{row}").Value = values[i]
        ws.Range(f"J{row}").Value = f"{confidences[i]} level of confidence in the evaluation"
        ws.Range(f"K{row}").Value = confidence_map.get(confidences[i], 1)

    ws.Range("F39").Value = amplification

    wb.RefreshAll()
    excel.CalculateFull()
    wb.SaveAs(export_path, FileFormat=51)
    wb.Close(SaveChanges=0)
    excel.Quit()

    with open(export_path, "rb") as f:
        data = f.read()

    download_name = f"{safe_name} evaluation result.xlsx"
    resp = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = (
        f'attachment; filename="{download_name}"; filename*=UTF-8\'\'{quote(download_name)}'
    )
    return resp


#------------------------------Scorecard--------------------------------------

xframe_options_sameorigin
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
    """Return minimal fields for the selector modal."""
    include_inactive = request.GET.get("inactive") == "1"
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        return JsonResponse({"ok": False, "error": "MongoDB not reachable"}, status=503)

    query = {} if include_inactive else {"is_active": True}
    proj = {"_id": 0, "id": 1, "name": 1, "macro": 1, "meso1": 1, "meso2": 1, "is_active": 1}
    docs = list(technologies.find(query, proj))
    # sort by name client-side for stability
    docs.sort(key=lambda d: (d.get("name") or "").lower())
    return JsonResponse({"ok": True, "items": docs})

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