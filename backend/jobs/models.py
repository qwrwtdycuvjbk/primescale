import uuid
from django.db import models
from django.conf import settings
from companies.models import Company


class Job(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"
        ARCHIVED = "archived", "Archived"

    class RoleType(models.TextChoices):
        CONTRACT = "contract", "Contract"
        C2H = "c2h", "Contract-to-Hire"
        FULL_TIME = "full-time", "Full-time"

    class ExperienceLevel(models.TextChoices):
        JUNIOR = "junior", "Junior"
        MID = "mid", "Mid-level"
        SENIOR = "senior", "Senior"
        LEAD = "lead", "Lead / Staff"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="jobs"
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posted_jobs"
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    role_type = models.CharField(max_length=30, choices=RoleType.choices)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices)
    tech_stack = models.JSONField(default=list, blank=True)
    salary_range = models.CharField(max_length=100, blank=True, null=True)
    work_type = models.CharField(max_length=20, default="remote")
    visa_requirements = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    expires_at = models.DateTimeField(blank=True, null=True)
    jd_quality_score = models.IntegerField(blank=True, null=True)
    jd_quality_feedback = models.TextField(blank=True, null=True)
    featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} at {self.company.name}"
