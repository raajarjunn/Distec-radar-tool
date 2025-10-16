

from django import template
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.urls import reverse
from django.shortcuts import render

from pymongo import MongoClient
from datetime import datetime 

from apps.common.activity_log import activities
from datetime import datetime, timezone



# -----------------------------------------Pymongo connection---------------------------------------------------------

client = MongoClient("mongodb://localhost:27017/") 
db = client["tech_tool_db"]
activities = db["activities"]   # collection name for recent activities


def _aware(dt):
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc)

@login_required(login_url="/login/")
def index(request):
    cursor = (
        activities.find(
            {},  # show all recent activities; filter if you want
            {"activity": 1, "username": 1, "occurred_at": 1, "logged_in": 1, "meta": 1}
        )
        .sort("occurred_at", -1)
        .limit(10)
    )

    rows = []
    for d in cursor:
        meta = d.get("meta") or {}
        tech_name = (
            meta.get("technology_name")
            or meta.get("name")
            or meta.get("technology")
            or meta.get("tech")
        )
        activity = d.get("activity", "")
        label = f"{activity} — {tech_name}" if tech_name else activity

        rows.append({
            "activity": label,                  # ← Activity / Technology
            "user": d.get("username", "—"),
            "time": _aware(d.get("occurred_at")),
            "logged_in": bool(d.get("logged_in", False)),
        })

    return render(request, "home/index.html", {"segment": "index", "rows": rows})



@login_required(login_url="/login/")
def pages(request):
    context = {}
    # All resource paths end in .html.
    # Pick out the html file name from the url. And load that template.
    try:

        load_template = request.path.split('/')[-1]

        if load_template == 'admin':
            return HttpResponseRedirect(reverse('admin:index'))
        context['segment'] = load_template

        html_template = loader.get_template('home/' + load_template)
        return HttpResponse(html_template.render(context, request))

    except template.TemplateDoesNotExist:

        html_template = loader.get_template('home/page-404.html')
        return HttpResponse(html_template.render(context, request))

    except:
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render(context, request))

def dashboard(request):
    rows = [
    {"activity": "/tech-tool/",                "time": 4569, "duration": 340, "rate": 46.53},
    {"activity": "/tech-tool/index.html",      "time": 3985, "duration": 319, "rate": -12.47},
    {"activity": "/tech-tool/charts.html",     "time": 3513, "duration": 294, "rate": -36.49},
    {"activity": "/tech-tool/tables.html",     "time": 2050, "duration": 147, "rate": 50.87},
    {"activity": "/tech-tool/profile.html",    "time": 1795, "duration": 190, "rate": -46.53},
    {"activity": "/reports/weekly",        "time": 1620, "duration": 132, "rate": 8.12},
    {"activity": "/api/v1/login",          "time": 5120, "duration": 88,  "rate": -5.31},
    {"activity": "/projects/alpha",        "time": 2488, "duration": 210, "rate": 17.40},
    {"activity": "/settings/organization", "time": 973,  "duration": 75,  "rate": -22.18},
    {"activity": "/help/faq",              "time": 1211, "duration": 64,  "rate": 4.96},
    ]

    return render(request, "home/templates/index.html", {"rows": rows}) 

