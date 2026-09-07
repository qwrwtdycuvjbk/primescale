from django.contrib import admin
from .models import CandidateProfile


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "current_title",
        "experience_level",
        "work_authorization",
        "availability_status",
        "profile_completeness",
        "profile_complete",
        "created_at",
    )
    list_filter = (
        "experience_level",
        "work_authorization",
        "availability_status",
        "privacy_visibility",
        "profile_complete",
        "open_to_matching",
    )
    search_fields = ("user__email", "headline", "current_title", "us_state")
    readonly_fields = ("created_at", "updated_at")
