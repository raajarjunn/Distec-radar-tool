from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps
from django.conf import settings

from .models import User

DEFAULT_USER_ROLE_NAME = "user1"

@receiver(post_save, sender=User)
def set_default_role_on_create(sender, instance: User, created: bool, **kwargs):
    """
    If a user is created without an explicit role, assign the default role 'user1'.
    Avoid saving the in-memory instance (which may not have a PK yet in Djongo).
    Instead, re-fetch a persisted row and update via queryset.
    """
    if not created:
        return
    if getattr(instance, "role_id", None):
        return

    Role = apps.get_model('authentication', 'Role')
    try:
        default_role = Role.objects.get(name=DEFAULT_USER_ROLE_NAME)
    except Role.DoesNotExist:
        return

    # Re-fetch a persisted copy (guarantees PK) by unique username
    db_user = User.objects.filter(username=instance.username).only("id").first()
    if not db_user:
        return  # nothing persisted yet; bail quietly

    # Assign via queryset update—doesn't require loading instance PK
    User.objects.filter(pk=db_user.pk).update(role=default_role)
