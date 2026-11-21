from django.contrib import admin
from .models import Match, ExternalJobEmbedding, ExternalJobRecommendation, ExternalJobRecommendationFeedback


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


@admin.register(ExternalJobEmbedding)
class ExternalJobEmbeddingAdmin(admin.ModelAdmin):
    list_display = (
        "external_job",
        "status",
        "model_name",
        "dimensions",
        "content_hash",
        "embedded_at",
        "created_at",
    )
    list_filter = ("status", "model_name")
    search_fields = ("external_job__title", "external_job__company_name", "content_hash")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ExternalJobRecommendation)
class ExternalJobRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "candidate_profile",
        "external_job",
        "final_score",
        "semantic_score",
        "skill_score",
        "experience_score",
        "calculated_at",
    )
    list_filter = ("matching_model",)
    search_fields = (
        "candidate_profile__user__email",
        "external_job__title",
        "external_job__company_name",
    )
    readonly_fields = ("created_at", "updated_at", "calculated_at")


@admin.register(ExternalJobRecommendationFeedback)
class ExternalJobRecommendationFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "candidate_profile",
        "recommendation",
        "reason",
        "created_at",
    )
    list_filter = ("reason", "created_at")
    search_fields = (
        "candidate_profile__user__email",
        "recommendation__external_job__title",
        "comments",
    )
    readonly_fields = ("id", "created_at", "updated_at")
