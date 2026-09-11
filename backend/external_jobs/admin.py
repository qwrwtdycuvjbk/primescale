from django.contrib import admin
from external_jobs.models import ExternalJob, ExternalJobSource


@admin.register(ExternalJobSource)
class ExternalJobSourceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "provider_code",
        "api_enabled",
        "attribution_name",
        "active_jobs_count",
        "last_sync_at",
        "last_sync_status",
    ]
    list_filter = ["api_enabled", "last_sync_status"]
    search_fields = ["name", "provider_code", "attribution_name"]
    readonly_fields = ["last_sync_at", "last_sync_status", "last_sync_error", "active_jobs_count", "created_at", "updated_at"]
    actions = ["enable_api", "disable_api"]

    @admin.action(description="Enable selected API sources")
    def enable_api(self, request, queryset):
        queryset.update(api_enabled=True)

    @admin.action(description="Disable selected API sources")
    def disable_api(self, request, queryset):
        queryset.update(api_enabled=False)


@admin.register(ExternalJob)
class ExternalJobAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "company_name",
        "source_name",
        "remote_type",
        "country",
        "status",
        "is_active",
        "posted_at",
    ]
    list_filter = ["remote_type", "status", "is_active", "country", "source_name"]
    search_fields = ["title", "company_name", "description", "external_job_id"]
    readonly_fields = [
        "id",
        "dedup_hash",
        "raw_metadata",
        "fetched_at",
        "last_seen_at",
        "created_at",
        "updated_at",
    ]
    actions = ["mark_active", "mark_inactive", "mark_expired"]

    @admin.action(description="Mark selected jobs as Active")
    def mark_active(self, request, queryset):
        queryset.update(status=ExternalJob.Status.ACTIVE, is_active=True)

    @admin.action(description="Mark selected jobs as Inactive")
    def mark_inactive(self, request, queryset):
        queryset.update(status=ExternalJob.Status.INACTIVE, is_active=False)

    @admin.action(description="Mark selected jobs as Expired")
    def mark_expired(self, request, queryset):
        queryset.update(status=ExternalJob.Status.EXPIRED, is_active=False)
