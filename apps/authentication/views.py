# apps\authentication\views.py
from time import perf_counter
import logging

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, get_user_model
from .forms import LoginForm, SignUpForm

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, UpdateView
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages

from apps.authentication.forms import AssignRoleForm
from apps.authentication.perm import ActionPermissionMixin, require_action
from bson import ObjectId 
from django.http import Http404, HttpResponse

logger = logging.getLogger(__name__)  # e.g. "apps.authentication.views"
User = get_user_model()


def _client_ip(request) -> str:
    """Best-effort client IP (handles proxies)."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "-"))


def login_view(request):
    t0 = perf_counter()
    form = LoginForm(request.POST or None)
    msg = None

    try:
        if request.method == "POST":
            if form.is_valid():
                username = form.cleaned_data.get("username")
                # DO NOT log the password
                logger.info("login_attempt user=%s ip=%s path=%s", username, _client_ip(request), request.path)

                user = authenticate(request, username=username, password=form.cleaned_data.get("password"))

                # Fallback: if backend returns a user without PK, re-fetch a persisted copy
                if user is None or getattr(user, "pk", None) is None:
                    logger.debug("login_fallback_check user=%s", username)
                    db_user = User.objects.filter(username=username).first()
                    if db_user and db_user.check_password(form.cleaned_data.get("password")):
                        user = db_user
                        logger.debug("login_fallback_hit user=%s pk=%s", username, getattr(user, "pk", None))

                if user is not None and getattr(user, "pk", None):
                    login(request, user)
                    logger.info("login_success user=%s pk=%s dur_ms=%.1f", username, user.pk, (perf_counter() - t0) * 1000)
                    return redirect("/")
                else:
                    msg = "Invalid credentials or user not saved correctly."
                    logger.warning("login_failed user=%s reason=%s ip=%s dur_ms=%.1f",
                                   username, "invalid_or_no_pk", _client_ip(request), (perf_counter() - t0) * 1000)
            else:
                msg = "Error validating the form"
                logger.warning("login_form_invalid errors=%s ip=%s dur_ms=%.1f",
                               dict(form.errors), _client_ip(request), (perf_counter() - t0) * 1000)

        resp = render(request, "accounts/login.html", {"form": form, "msg": msg})
        logger.debug("login_view_render status=%s dur_ms=%.1f", getattr(resp, "status_code", "-"), (perf_counter() - t0) * 1000)
        return resp

    except Exception:
        logger.exception("login_view_exception ip=%s", _client_ip(request))
        # Keep the same UX on error
        msg = "Unexpected error, please try again."
        return render(request, "accounts/login.html", {"form": form, "msg": msg})


def register_user(request):
    t0 = perf_counter()
    msg = None
    success = False

    try:
        if request.method == "POST":
            form = SignUpForm(request.POST)
            if form.is_valid():
                # If your SignUpForm.save() returns the user, you can log it
                user = form.save()
                logger.info("register_success user=%s pk=%s ip=%s dur_ms=%.1f",
                            getattr(user, "username", "-"), getattr(user, "pk", None), _client_ip(request), (perf_counter() - t0) * 1000)

                # If you want to verify auth pipeline, uncomment:
                # auth_user = authenticate(request, username=user.username, password=form.cleaned_data.get("password1"))
                # logger.debug("register_authenticate_check user=%s ok=%s", user.username, bool(auth_user))

                msg = 'User created - please <a href="/login">login</a>.'
                success = True
                return redirect("/login/")
            else:
                msg = "Form is not valid"
                logger.warning("register_form_invalid errors=%s ip=%s dur_ms=%.1f",
                               dict(form.errors), _client_ip(request), (perf_counter() - t0) * 1000)
        else:
            form = SignUpForm()
            logger.debug("register_form_init ip=%s", _client_ip(request))

        resp = render(request, "accounts/register.html", {"form": form, "msg": msg, "success": success})
        logger.debug("register_view_render status=%s dur_ms=%.1f", getattr(resp, "status_code", "-"), (perf_counter() - t0) * 1000)
        return resp

    except Exception:
        logger.exception("register_view_exception ip=%s", _client_ip(request))
        msg = "Unexpected error, please try again."
        form = SignUpForm()
        return render(request, "accounts/register.html", {"form": form, "msg": msg, "success": False})
    


class UserRoleListView(LoginRequiredMixin, ActionPermissionMixin, ListView):
    required_action = "manage_roles"
    model = User
    template_name = "accounts/role.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        q = (self.request.GET.get("q") or "").strip()
        qs = User.objects.all().select_related("role").order_by("username")
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
        return qs

class UserRoleUpdateView(LoginRequiredMixin, ActionPermissionMixin, UpdateView):
    required_action = "manage_roles"
    model = User
    form_class = AssignRoleForm
    template_name = "accounts/edit.html"
    success_url = reverse_lazy("role_admin_list")

    def get_object(self, queryset=None):
        pk = self.kwargs.get("pk")
        qs = queryset or self.get_queryset()
        try:
            return qs.get(pk=pk)
        except self.model.DoesNotExist:
            pass
        try:
            return qs.get(pk=ObjectId(pk))
        except (self.model.DoesNotExist, Exception):
            pass
        obj = (self.model.objects.filter(id=pk).first()
               or self.model.objects.filter(id=ObjectId(pk)).first())
        if obj:
            return obj
        raise Http404("User not found")
    
    def get_template_names(self):
        # If this is an HTMX request, return the partial used inside the modal
        if self.request.headers.get("HX-Request"):
            return ["accounts/edit.html"]
        return [self.template_name]

    def form_valid(self, form):
        messages.success(self.request, "User role updated.")
        response = super().form_valid(form)

        # If HTMX, trigger client-side event to close modal + refresh list
        if self.request.headers.get("HX-Request"):
            resp = HttpResponse("<div class='p-3'>Saved.</div>")
            resp["HX-Trigger"] = "roleSaved"
            return resp

        # Normal POST: follow success_url redirect
        return response