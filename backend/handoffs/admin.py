from django.contrib import admin
from .models import HandoffRequest


@admin.register(HandoffRequest)
class HandoffRequestAdmin(admin.ModelAdmin):
    list_display = ("match", "status", "notified_at", "created_at")
    list_filter = ("status",)
    search_fields = (
        "match__candidate_profile__user__email",
        "match__job__title",
        "match__job__company__name",
    )
    readonly_fields = ("created_at", "updated_at")
