from django import template
from apps.authentication.perm import user_has_permission

register = template.Library()

@register.filter
def can(user, action: str):
    try:
        return user_has_permission(user, action)
    except Exception:
        return False