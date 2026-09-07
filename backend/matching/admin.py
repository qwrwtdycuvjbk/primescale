from django.contrib import admin
from .models import Match


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "candidate_profile",
        "job",
        "match_score",
        "status",
        "visible_to_employer",
        "recruiter_notified_at",
        "created_at",
    )
    list_filter = ("status", "visible_to_employer")
    search_fields = ("candidate_profile__user__email", "job__title", "job__company__name")
    readonly_fields = ("created_at", "updated_at")
