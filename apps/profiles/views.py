# apps/profiles/views.py
import logging
import hashlib
from django.db import transaction
from time import perf_counter

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms.models import model_to_dict
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from bson import ObjectId

from .forms import ProfileForm

logger = logging.getLogger(__name__)
User = get_user_model()

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5MB

def _uinfo(u):
    try:
        rid = getattr(u, "role_id", None)
        rname = getattr(getattr(u, "role", None), "name", None)
        return f"username={u.username} pk={u.pk} role_id={rid} role={rname}"
    except Exception:
        return f"user(pk={getattr(u, 'pk', None)})"

def ping(request):
    logger.info("PING start path=%s method=%s", request.path, request.method)
    resp = HttpResponse("pong")
    logger.info("PING ok status=%s", resp.status_code)
    return resp

def _persist_avatar_from_upload(user, upload):
    """
    Validate + store avatar into DB columns: avatar_blob, avatar_mime, avatar_sha1.
    Returns (changed: bool, msg: str). Raises ValueError for invalid input.
    """
    ctype = (getattr(upload, "content_type", None) or "").lower()
    size = getattr(upload, "size", 0)

    if ctype not in ALLOWED_MIME:
        raise ValueError("Unsupported file type. Please upload JPG/PNG/WebP.")
    if size > MAX_AVATAR_BYTES:
        raise ValueError("Avatar too large (max 5MB).")

    blob = upload.read()
    sha1 = hashlib.sha1(blob).hexdigest()

    if sha1 == (user.avatar_sha1 or ""):
        return (False, "Avatar unchanged (same image).")

    user.avatar_blob = blob
    user.avatar_mime = ctype or "application/octet-stream"
    user.avatar_sha1 = sha1
    user.save(update_fields=["avatar_blob", "avatar_mime", "avatar_sha1"])
    logger.info("avatar saved uid=%s bytes=%s mime=%s sha1=%s", user.pk, len(blob), user.avatar_mime, sha1)
    return (True, "Avatar updated.")



@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request):
    t0 = perf_counter()
    logger.info("profile_view start method=%s path=%s uid=%s",
                request.method, request.path, request.user.pk)

    # Load user + role/permissions
    try:
        u = (User.objects
                .select_related("role")
                .prefetch_related("role__permissions")
                .get(pk=request.user.pk))
        logger.debug("profile_view user %s", _uinfo(u))
    except Exception:
        logger.exception("profile_view failed to load user pk=%s", request.user.pk)
        return HttpResponse("Unable to load profile", status=500)

    role_permissions = list(u.role.permissions.values_list("permission", flat=True)) if u.role_id else []
    can_admin = any(p in role_permissions for p in ("edit_users", "delete_users"))
    # NEW: any authenticated user can edit **their own** profile here
    can_edit = True

    # --- AVATAR PRECHECK (name=avatar_file) ---
    incoming_file = request.FILES.get("avatar_file")
    avatar_confirmed = request.POST.get("avatar_confirmed") == "1"
    logger.debug("avatar_precheck file_present=%s confirmed=%s file_keys=%s",
                 bool(incoming_file), avatar_confirmed, list(request.FILES.keys()))

    if request.method == "POST":
        # NOTE: This profile view is always "self". So allow POST for any logged-in user.
        # If you later allow editing other users here, protect with:
        # if u.pk != request.user.pk and not can_admin: return HttpResponseForbidden(...)

        # If a file was chosen but not confirmed, bounce with a message
        if incoming_file and not avatar_confirmed:
            messages.warning(request, "Click “Use this photo” to confirm the new avatar, then Save.")
            logger.info("profile_view avatar chosen but not confirmed uid=%s", request.user.pk)
            return redirect("profile")

        logger.debug("profile_view POST data uid=%s POST=%s FILES=%s",
                     request.user.pk, request.POST.dict(), list(request.FILES.keys()))

        form = ProfileForm(request.POST, request.FILES, instance=u)
        if form.is_valid():
            before = model_to_dict(u, fields=form.fields.keys())
            saved = form.save()
            after = model_to_dict(saved, fields=form.fields.keys())
            changed = {k: (before.get(k), after.get(k)) for k in after if before.get(k) != after.get(k)}
            logger.info("profile_view updated uid=%s field_changes=%s", request.user.pk, changed)

            # ---- AVATAR (DB) via helper -------------------------------------
            f = request.FILES.get("avatar_file")
            if f and avatar_confirmed:
                try:
                    changed, msg = _persist_avatar_from_upload(u, f)
                    if changed:
                        messages.success(request, msg)
                    else:
                        messages.info(request, msg)
                except ValueError as ve:
                    messages.error(request, str(ve))
                    logger.warning("profile_view avatar validation failed uid=%s err=%s", request.user.pk, ve)
                except Exception:
                    logger.exception("profile_view avatar update failed uid=%s", request.user.pk)
                    messages.error(request, "Could not save avatar. Please try again.")
            else:
                logger.debug("avatar_save skipped (file=%s confirmed=%s)", bool(f), avatar_confirmed)
            # ------------------------------------------------------------------

            messages.success(request, "Profile updated.")
            return redirect("profile")
        else:
            logger.warning("profile_view invalid_form uid=%s errors=%s", request.user.pk, dict(form.errors))
    else:
        form = ProfileForm(instance=u)
        logger.debug("profile_view GET form initialized uid=%s", request.user.pk)

    resp = render(request, "profile.html", {
        "u": u,
        "form": form,
        "role_name": u.role.name if u.role_id else "",
        "role_permissions": role_permissions,
        "can_edit": can_edit,     # ALWAYS True for self-profile
        "can_admin": can_admin,   # NEW: for UI badge/logic
    })
    logger.info("profile_view ok uid=%s status=%s dur_ms=%.1f",
                request.user.pk, resp.status_code, (perf_counter()-t0)*1000)
    return resp


@login_required
@require_http_methods(["POST"])
def delete_account(request):
    t0 = perf_counter()
    logger.info("delete_account start uid=%s path=%s", request.user.pk, request.path)
    u = get_object_or_404(User, pk=request.user.pk)
    logger.warning("delete_account deleting %s", _uinfo(u))
    u.delete()
    messages.success(request, "Account deleted.")
    logger.info("delete_account ok dur_ms=%.1f", (perf_counter() - t0) * 1000)
    return redirect("login")

@login_required
def profile_dump(request):
    t0 = perf_counter()
    logger.info("profile_dump start uid=%s path=%s", request.user.pk, request.path)
    try:
        u = (User.objects
                .select_related("role")
                .prefetch_related("role__permissions")
                .get(pk=request.user.pk))
        logger.debug("profile_dump user %s", _uinfo(u))

        user_fields = [
            "id", "username", "email", "first_name", "last_name",
            "full_name", "phone_number", "date_of_birth", "gender",
            "alternate_email", "address_line1", "address_line2",
            "city", "state", "country", "postcode",
            "timezone", "language_preference",
            "last_login", "date_joined", "is_active",
            "is_staff", "is_super_admin",
        ]
        data = model_to_dict(u, fields=[f for f in user_fields if hasattr(u, f)])
        data["role"] = u.role.name if getattr(u, "role_id", None) else None
        data["role_permissions"] = list(u.role.permissions.values_list("permission", flat=True)) if getattr(u, "role_id", None) else []
        data["avatar_url"] = request.build_absolute_uri(f"/profile/avatar/{u.pk}/")

        logger.debug("profile_dump keys=%s", list(data.keys()))
        resp = JsonResponse(data, safe=False)
        logger.info("profile_dump ok status=%s dur_ms=%.1f", resp.status_code, (perf_counter() - t0) * 1000)
        return resp
    except Exception:
        logger.exception("profile_dump error uid=%s", request.user.pk)
        return JsonResponse({"error": "internal error"}, status=500)

@login_required
def profile_avatar(request, user_id: str):
    """Streams avatar bytes from DB with ETag/304; owner only."""
    t0 = perf_counter()
    logger.info("profile_avatar start path=%s viewer=%s target_param=%s", request.path, request.user.pk, user_id)

    try:
        pk = ObjectId(user_id) if isinstance(user_id, str) else user_id
    except Exception:
        logger.warning("profile_avatar invalid ObjectId: %s", user_id)
        return HttpResponse(status=404)

    u = get_object_or_404(User, pk=pk)

    if u.pk != request.user.pk:
        logger.warning("profile_avatar forbidden viewer=%s target=%s", request.user.pk, u.pk)
        return HttpResponseForbidden("Forbidden")

    if not getattr(u, "avatar_blob", None):
        logger.info("profile_avatar no avatar; redirecting to placeholder uid=%s", request.user.pk)
        return HttpResponseRedirect('/static/assets/img/theme/team-4.jpg')

    etag = f'"{u.avatar_sha1 or ""}"'
    if request.headers.get("If-None-Match") == etag:
        logger.info("profile_avatar 304 uid=%s", request.user.pk)
        return HttpResponse(status=304)

    mime = u.avatar_mime or "application/octet-stream"
    resp = HttpResponse(u.avatar_blob, content_type=mime)
    resp["ETag"] = etag
    resp["Cache-Control"] = "private, max-age=3600"
    logger.info("profile_avatar ok uid=%s bytes=%s mime=%s dur_ms=%.1f",
                request.user.pk, len(u.avatar_blob or b""), mime, (perf_counter()-t0)*1000)
    return resp
