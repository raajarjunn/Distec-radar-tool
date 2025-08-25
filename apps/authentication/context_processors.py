def user_context(request):
    """
    Adds 'u' (enriched user), 'role_name', and 'role_permissions' to every template.
    Safe for anonymous users. Avoids get_user_model at import time.
    """
    if not request.user.is_authenticated:
        return {"u": None, "role_name": "", "role_permissions": []}

    # cache per request
    cached = getattr(request, "_enriched_user_cache", None)
    if cached:
        return cached

    # import lazily so apps are ready
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # keep it simple first; add .only(...) later after it boots
    qs = (User.objects
            .select_related("role")
            .prefetch_related("role__permissions"))

    u = qs.get(pk=request.user.pk)

    role_name = u.role.name if getattr(u, "role_id", None) else ""
    role_permissions = list(u.role.permissions.values_list("permission", flat=True)) if u.role_id else []

    ctx = {"u": u, "role_name": role_name, "role_permissions": role_permissions}
    setattr(request, "_enriched_user_cache", ctx)
    return ctx
