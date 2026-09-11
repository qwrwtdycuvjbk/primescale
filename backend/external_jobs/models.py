import uuid
from django.db import models


class ExternalJobSource(models.Model):
    class SyncStatus(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILURE = "FAILURE", "Failure"
        RUNNING = "RUNNING", "Running"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    provider_code = models.CharField(max_length=100, unique=True)
    api_enabled = models.BooleanField(default=False)
    attribution_name = models.CharField(max_length=255)
    attribution_url = models.URLField(max_length=500, blank=True, null=True)
    last_sync_at = models.DateTimeField(blank=True, null=True)
    last_sync_status = models.CharField(
        max_length=50, choices=SyncStatus.choices, blank=True, null=True
    )
    last_sync_error = models.TextField(blank=True, null=True)
    active_jobs_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_job_sources"
        ordering = ["name"]
        verbose_name = "External Job Source"
        verbose_name_plural = "External Job Sources"

    def __str__(self):
        return f"{self.name} ({self.provider_code})"


class ExternalJob(models.Model):
    class RemoteType(models.TextChoices):
        REMOTE = "REMOTE", "Remote"
        HYBRID = "HYBRID", "Hybrid"
        ONSITE = "ONSITE", "Onsite"
        UNKNOWN = "UNKNOWN", "Unknown"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        ExternalJobSource, on_delete=models.CASCADE, related_name="jobs"
    )
    external_job_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    company_website = models.URLField(max_length=500, blank=True, null=True)
    description = models.TextField()
    location = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=10, default="US")
    state = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    remote_type = models.CharField(
        max_length=20, choices=RemoteType.choices, default=RemoteType.UNKNOWN
    )
    employment_type = models.CharField(max_length=50, blank=True, null=True)
    salary_min = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    salary_max = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    salary_currency = models.CharField(max_length=10, default="USD")
    tech_stack = models.JSONField(default=list, blank=True)
    original_job_url = models.URLField(max_length=1000)
    source_job_url = models.URLField(max_length=1000, blank=True, null=True)
    source_name = models.CharField(max_length=100)
    posted_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    is_active = models.BooleanField(default=True)
    dedup_hash = models.CharField(max_length=64, db_index=True, blank=True, null=True)
    raw_metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_jobs"
        ordering = ["-posted_at", "-created_at"]
        verbose_name = "External Job"
        verbose_name_plural = "External Jobs"
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_job_id"],
                name="unique_source_external_job",
            )
        ]
        indexes = [
            models.Index(
                fields=["country", "remote_type", "is_active", "status"],
                name="idx_extjob_country_remote_act",
            )
        ]

    def __str__(self):
        return f"{self.title} at {self.company_name} ({self.source_name})"
