import uuid
from django.db import models


class JobLead(models.Model):
    """
    Extensible Job Lead model for future external providers or saved remote tech leads.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_id = models.CharField(max_length=255, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    company_website = models.URLField(blank=True, null=True, max_length=1000)
    apply_url = models.URLField(blank=True, null=True, max_length=2000)
    publisher = models.CharField(max_length=255, blank=True, null=True)
    posted_at = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    employment_type = models.CharField(max_length=100, blank=True, null=True)
    is_remote = models.BooleanField(default=True)
    description_preview = models.TextField(blank=True, null=True)
    source_locale = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "job_leads"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} at {self.company}"


class RoleSubmission(models.Model):
    """
    Submissions from public 'Hire Talent' / 'Post Role' lead-generation form.
    Replaces legacy Supabase role_submissions table.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    company_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=50)
    job_title = models.CharField(max_length=255)
    role_type = models.CharField(max_length=50)
    experience_level = models.CharField(max_length=50)
    tech_stack = models.TextField()
    salary_range = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField()
    notes = models.TextField(blank=True, null=True)
    submission_type = models.CharField(max_length=50, default="manual_form")

    class Meta:
        db_table = "role_submissions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.job_title} at {self.company_name} ({self.contact_name})"
