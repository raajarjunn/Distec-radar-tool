# apps/authentication/perm.py
from pymongo import MongoClient
import os, fnmatch
from django.http import HttpResponseForbidden


# 1) Connect once (env vars or literals)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB  = os.getenv("MONGO_DB",  "tech_tool_db")

_client = MongoClient(MONGO_URI)
_db = _client[MONGO_DB]

# Keep your *technology* collection separate (if you need it elsewhere)
technology_col = _db["technology_technology"]     # <-- your actual tech docs

# Permissions mapping lives here
role_permissions_col = _db["role_permissions"]    # <-- clear, no shadowing

class ActionPermissionMixin:
    """
    Use on class-based views:
      class MyView(LoginRequiredMixin, ActionPermissionMixin, View):
          required_action = "add_technology"
    """
    required_action = None
    login_url_name = "login"   # change if your login url name differs


def user_has_permission(user, action: str) -> bool:
    """Return True if the user's role has the given action (exact or wildcard)."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "isSuperAdmin", False):
        return True

    # If your User model stores a Role object with numeric 'id'
    role = getattr(user, "role", None)
    role_id = getattr(role, "id", None) or getattr(user, "role_id", None)
    if role_id is None:
        return False

    # Fetch all permissions for this role_id (materialized list)
    perms = list(role_permissions_col.find(
        {"role_id": int(role_id)},
        {"_id": 0, "permission": 1}
    ))
    patterns = [p["permission"] for p in perms]

    # Support both exact strings and simple wildcards like "view_*"
    return any(fnmatch.fnmatch(action, pat) for pat in patterns)

def require_action(action: str):
    def _wrap(fn):
        def _inner(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Not allowed")
            if not user_has_permission(request.user, action):
                return HttpResponseForbidden("Not allowed")
            return fn(request, *args, **kwargs)
        return _inner
    return _wrap

