import uuid
from django.db import models
from django.conf import settings


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_company",
    )
    name = models.CharField(max_length=255)
    website = models.URLField(max_length=500, blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=100, default="US")
    logo_url = models.CharField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    hq_city = models.CharField(max_length=100, blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    remote_culture_statement = models.TextField(blank=True, null=True)
    domain_verified = models.BooleanField(default=False)
    profile_complete = models.BooleanField(default=False)

    badge_remote_first = models.BooleanField(default=False)
    badge_visa_sponsor = models.BooleanField(default=False)
    badge_gcc = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "companies"
        verbose_name_plural = "companies"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class CompanyMember(models.Model):
    class MemberRole(models.TextChoices):
        ADMIN = "admin", "Admin"
        RECRUITER = "recruiter", "Recruiter"
        HIRING_MANAGER = "hiring_manager", "Hiring Manager"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_memberships"
    )
    member_role = models.CharField(
        max_length=30, choices=MemberRole.choices, default=MemberRole.ADMIN
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "company_members"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user"], name="unique_company_member"
            )
        ]

    def __str__(self):
        return f"{self.user.email} - {self.company.name} ({self.member_role})"
