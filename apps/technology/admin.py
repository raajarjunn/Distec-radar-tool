from django.contrib import admin
from .models import Technology

@admin.register(Technology)
class TechnologyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "macro", "is_active", "confidentiality", "last_modified")
    list_filter = ("is_active", "confidentiality", "macro")
    search_fields = ("name", "macro", "meso1", "meso2", "description")
    readonly_fields = ("created_at", "last_modified")
