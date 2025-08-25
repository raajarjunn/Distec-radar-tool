from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Role

admin.site.register(Role)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role', 'is_super_admin')}),
    )
