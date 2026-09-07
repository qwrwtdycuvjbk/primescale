import uuid
from django.db import models
from django.conf import settings


class CandidateProfile(models.Model):
    class ExperienceLevel(models.TextChoices):
        JUNIOR = "junior", "Junior"
        MID = "mid", "Mid-level"
        SENIOR = "senior", "Senior"
        LEAD = "lead", "Lead / Staff"

    class WorkAuthorization(models.TextChoices):
        US_CITIZEN = "us_citizen", "US Citizen"
        GREEN_CARD = "green_card", "Green Card"
        H1B = "h1b", "H1-B"
        EAD = "ead", "EAD"
        INTERNATIONAL_REMOTE = "international_remote", "International Remote"

    class PreferredWorkType(models.TextChoices):
        REMOTE = "remote", "Remote"
        HYBRID = "hybrid", "Hybrid"
        ONSITE = "onsite", "Onsite"

    class AvailabilityStatus(models.TextChoices):
        ACTIVELY_LOOKING = "actively_looking", "Actively Looking"
        OPEN = "open", "Open to Opportunities"
        NOT_LOOKING = "not_looking", "Not Looking"

    class PrivacyVisibility(models.TextChoices):
        PUBLIC = "public", "Public"
        EMPLOYERS_ONLY = "employers_only", "Employers Only"
        INVITE_ONLY = "invite_only", "Invite Only"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    headline = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    current_title = models.CharField(max_length=255, blank=True, null=True)
    years_experience = models.IntegerField(blank=True, null=True)

    # JSONField/JSON array to preserve skills and role categories across DB engines (PostgreSQL/SQLite)
    skills = models.JSONField(default=list, blank=True)
    role_categories = models.JSONField(default=list, blank=True)

    experience_level = models.CharField(
        max_length=20, choices=ExperienceLevel.choices, blank=True, null=True
    )
    salary_min = models.IntegerField(blank=True, null=True)
    salary_max = models.IntegerField(blank=True, null=True)
    work_authorization = models.CharField(
        max_length=30, choices=WorkAuthorization.choices, blank=True, null=True
    )
    us_state = models.CharField(max_length=100, blank=True, null=True)
    remote_preference = models.CharField(max_length=50, default="remote")
    preferred_work_type = models.CharField(
        max_length=20, choices=PreferredWorkType.choices, default=PreferredWorkType.REMOTE
    )
    resume_url = models.CharField(max_length=500, blank=True, null=True)
    github_url = models.URLField(max_length=500, blank=True, null=True)
    portfolio_url = models.URLField(max_length=500, blank=True, null=True)
    linkedin_url = models.URLField(max_length=500, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    availability_status = models.CharField(
        max_length=30,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.ACTIVELY_LOOKING,
    )
    privacy_visibility = models.CharField(
        max_length=30,
        choices=PrivacyVisibility.choices,
        default=PrivacyVisibility.EMPLOYERS_ONLY,
    )
    profile_completeness = models.IntegerField(default=0)
    open_to_matching = models.BooleanField(default=True)
    profile_complete = models.BooleanField(default=False)
    source = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "candidate_profiles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Candidate Profile: {self.user.email}"
