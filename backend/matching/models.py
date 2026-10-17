import uuid
from django.db import models
from candidates.models import CandidateProfile
from jobs.models import Job


from django.core.exceptions import ValidationError
from pgvector.django import VectorField

TARGET_EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b"
TARGET_EMBEDDING_DIMENSIONS = 2048


class EmbeddingStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class Match(models.Model):
    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        CANDIDATE_INTERESTED = "candidate_interested", "Candidate Interested"
        EMPLOYER_SHORTLISTED = "employer_shortlisted", "Employer Shortlisted"
        MUTUAL_FIT = "mutual_fit", "Mutual Fit"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate_profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="matches"
    )
    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="matches"
    )
    match_score = models.IntegerField(default=0)
    match_reason = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.SUGGESTED
    )
    visible_to_employer = models.BooleanField(default=False)
    recruiter_notified_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "matches"
        verbose_name_plural = "matches"
        ordering = ["-match_score", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate_profile", "job"], name="unique_candidate_job_match"
            )
        ]

    def __str__(self):
        return f"Match ({self.match_score}%): {self.candidate_profile.user.email} -> {self.job.title}"


class CandidateResumeEmbedding(models.Model):
    """
    Private storage model for candidate resume text processing state,
    extracted metadata, and 2,048-dimensional embeddings.
    Strictly internal: never exposed through candidate/employer serializers.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate_profile = models.OneToOneField(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="resume_embedding",
    )
    status = models.CharField(
        max_length=20,
        choices=EmbeddingStatus.choices,
        default=EmbeddingStatus.PENDING,
        db_index=True,
    )
    model_name = models.CharField(
        max_length=100,
        default=TARGET_EMBEDDING_MODEL,
    )
    dimensions = models.IntegerField(default=TARGET_EMBEDDING_DIMENSIONS)
    embedding = VectorField(
        dimensions=TARGET_EMBEDDING_DIMENSIONS,
        null=True,
        blank=True,
    )
    extracted_text = models.TextField(
        blank=True,
        null=True,
        help_text="Normalized plain text extracted from candidate resume file. Strictly private.",
    )
    content_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text="SHA-256 fingerprint of the extracted resume text to avoid redundant embedding generation.",
    )
    text_length = models.IntegerField(
        default=0,
        help_text="Character count of extracted resume text.",
    )
    version = models.CharField(max_length=50, default="v1")
    error_message = models.TextField(blank=True, null=True)
    embedded_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "candidate_resume_embeddings"
        ordering = ["-updated_at"]

    def clean(self):
        super().clean()
        if self.dimensions != TARGET_EMBEDDING_DIMENSIONS:
            raise ValidationError(
                f"Invalid embedding dimensions: expected {TARGET_EMBEDDING_DIMENSIONS}, got {self.dimensions}."
            )
        if self.model_name != TARGET_EMBEDDING_MODEL:
            raise ValidationError(
                f"Invalid model name: expected '{TARGET_EMBEDDING_MODEL}', got '{self.model_name}'."
            )
        if self.embedding is not None and len(self.embedding) != TARGET_EMBEDDING_DIMENSIONS:
            raise ValidationError(
                f"Embedding vector length mismatch: expected {TARGET_EMBEDDING_DIMENSIONS}, got {len(self.embedding)}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"ResumeEmbedding ({self.status}): {self.candidate_profile_id}"


class JobEmbedding(models.Model):
    """
    Private storage model for normalized job description text metadata
    and 2,048-dimensional embeddings.
    Strictly internal: never exposed through public/employer job serializers.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField(
        Job,
        on_delete=models.CASCADE,
        related_name="job_embedding",
    )
    status = models.CharField(
        max_length=20,
        choices=EmbeddingStatus.choices,
        default=EmbeddingStatus.PENDING,
        db_index=True,
    )
    model_name = models.CharField(
        max_length=100,
        default=TARGET_EMBEDDING_MODEL,
    )
    dimensions = models.IntegerField(default=TARGET_EMBEDDING_DIMENSIONS)
    embedding = VectorField(
        dimensions=TARGET_EMBEDDING_DIMENSIONS,
        null=True,
        blank=True,
    )
    content_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text="SHA-256 fingerprint of the normalized job text to avoid redundant embedding generation.",
    )
    text_length = models.IntegerField(
        default=0,
        help_text="Character count of normalized job description text.",
    )
    version = models.CharField(max_length=50, default="v1")
    error_message = models.TextField(blank=True, null=True)
    embedded_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "job_embeddings"
        ordering = ["-updated_at"]

    def clean(self):
        super().clean()
        if self.dimensions != TARGET_EMBEDDING_DIMENSIONS:
            raise ValidationError(
                f"Invalid embedding dimensions: expected {TARGET_EMBEDDING_DIMENSIONS}, got {self.dimensions}."
            )
        if self.model_name != TARGET_EMBEDDING_MODEL:
            raise ValidationError(
                f"Invalid model name: expected '{TARGET_EMBEDDING_MODEL}', got '{self.model_name}'."
            )
        if self.embedding is not None and len(self.embedding) != TARGET_EMBEDDING_DIMENSIONS:
            raise ValidationError(
                f"Embedding vector length mismatch: expected {TARGET_EMBEDDING_DIMENSIONS}, got {len(self.embedding)}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        job_title = self.job.title if hasattr(self, 'job') and self.job else ''
        return f"JobEmbedding ({self.status}): {self.job_id} ({job_title})"
