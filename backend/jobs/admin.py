from django.contrib import admin
from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "posted_by",
        "role_type",
        "experience_level",
        "status",
        "expires_at",
        "created_at",
    )
    list_filter = ("status", "role_type", "experience_level", "featured")
    search_fields = ("title", "company__name", "posted_by__email", "description")
    readonly_fields = ("created_at", "updated_at")
