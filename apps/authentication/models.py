from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _
from djongo import models as dj
from bson import ObjectId

class Role(models.Model):
    id = dj.ObjectIdField(primary_key=True, default=ObjectId)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "user_role"
        verbose_name_plural = "roles"

    def __str__(self):
        return self.name


class User(AbstractUser):
    # Core
    id = dj.ObjectIdField(primary_key=True, default=ObjectId, db_column="_id")
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    is_super_admin = models.BooleanField(default=False)

    # Personal info
    full_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)  # e.g. Male/Female/Other

    # Contact info
    alternate_email = models.EmailField(blank=True, null=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postcode = models.CharField(max_length=20, blank=True)

    # Preferences
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    timezone = models.CharField(max_length=50, default='UTC')
    language_preference = models.CharField(max_length=20, default='en')
    avatar = models.URLField(blank=True)

    # Security & auth extras
    last_password_change = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=255, blank=True, null=True)

    # Audit info
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=150, blank=True)
    updated_by = models.CharField(max_length=150, blank=True)

    # New DB-backed avatar storage
    
    avatar_blob = models.BinaryField(blank=True, null=True, editable=False)
    avatar_mime = models.CharField(max_length=100, blank=True, default="")
    avatar_sha1 = models.CharField(max_length=40, blank=True, default="", editable=False)

    class Meta:
        db_table = "user"

    # Override AbstractUser M2M table names
    groups = models.ManyToManyField(
        Group,
        verbose_name=_("groups"),
        blank=True,
        help_text=_("The groups this user belongs to."),
        related_name="custom_user_set",
        related_query_name="user",
        db_table="user_groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_("user permissions"),
        blank=True,
        help_text=_("Specific permissions for this user."),
        related_name="custom_user_perm_set",
        related_query_name="user",
        db_table="user_permissions",
    )

    def has_role(self, role_name):
        return self.role and self.role.name.lower() == role_name.lower()

    def __str__(self):
        return self.username


class RolePermission(models.Model):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='permissions'
    )
    permission = models.CharField(max_length=100)

    class Meta:
        db_table = "role_permission"
        unique_together = ('role', 'permission')
        indexes = [
            models.Index(fields=['role', 'permission']),
        ]

    def __str__(self):
        return f"{self.role.name}:{self.permission}"


# Helper functions
def role_has_permission(role: Role, perm: str) -> bool:
    if not role:
        return False
    return role.permissions.filter(permission=perm).exists()

def user_has_permission(user: "User", perm: str) -> bool:
    if not user or not getattr(user, 'role_id', None):
        return False
    return user.role.permissions.filter(permission=perm).exists()
