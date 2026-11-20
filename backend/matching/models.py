import uuid
from django.db import models
from candidates.models import CandidateProfile
from jobs.models import Job
from external_jobs.models import ExternalJob


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
    extracted_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Deterministic technical skills extracted from normalized resume text. Kept strictly distinct from candidate-entered profile skills.",
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


class ExternalJobEmbedding(models.Model):
    """
    Private storage model for normalized external job description metadata
    and 2,048-dimensional embeddings.
    Strictly internal: never exposed through public external job serializers.
    Prevents duplicate embeddings per external job and supports fingerprint-based updates.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_job = models.OneToOneField(
        ExternalJob,
        on_delete=models.CASCADE,
        related_name="embedding_record",
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
        help_text="SHA-256 fingerprint of the external job text to avoid redundant embedding generation.",
    )
    text_length = models.IntegerField(
        default=0,
        help_text="Character count of normalized external job text.",
    )
    version = models.CharField(max_length=50, default="v1")
    error_message = models.TextField(blank=True, null=True)
    embedded_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_job_embeddings"
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
        ext_title = self.external_job.title if hasattr(self, 'external_job') and self.external_job else ''
        return f"ExternalJobEmbedding ({self.status}): {self.external_job_id} ({ext_title})"


class ExternalJobRecommendation(models.Model):
    """
    Stores qualified AI recommendations (final_score >= 70) for candidates
    matched against external job board listings (Adzuna, Himalayas, etc.).
    Completely isolated from first-party ATS Match and HandoffRequest models.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate_profile = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="external_recommendations",
    )
    external_job = models.ForeignKey(
        ExternalJob,
        on_delete=models.CASCADE,
        related_name="candidate_recommendations",
    )
    semantic_score = models.FloatField(
        default=0.0,
        help_text="Cosine similarity score (0.0 to 100.0) with 50% weight in final hybrid score.",
    )
    skill_score = models.FloatField(
        default=0.0,
        help_text="Skill overlap score (0.0 to 100.0) with 30% weight in final hybrid score.",
    )
    experience_score = models.FloatField(
        default=0.0,
        help_text="Experience level score (0.0 to 100.0) with 20% weight in final hybrid score.",
    )
    final_score = models.FloatField(
        db_index=True,
        help_text="Final hybrid score (0.0 to 100.0). Only recommendations with >= 70.0 qualify.",
    )
    matched_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="List of skills shared between the candidate and the external job.",
    )
    match_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Explanation breakdown of the hybrid match score.",
    )
    matching_model = models.CharField(
        max_length=100,
        default=TARGET_EMBEDDING_MODEL,
        help_text="Embedding model identifier used for recommendation calculation.",
    )
    embedding_version = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Fingerprint/version of the candidate resume embedding at calculation time.",
    )
    calculated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="Timestamp of most recent score calculation or refresh.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_job_recommendations"
        ordering = ["-final_score", "-created_at"]
        verbose_name = "External Job Recommendation"
        verbose_name_plural = "External Job Recommendations"
        constraints = [
            models.UniqueConstraint(
                fields=["candidate_profile", "external_job"],
                name="unique_candidate_external_job_recommendation",
            ),
            models.CheckConstraint(
                check=models.Q(final_score__gte=70.0) & models.Q(final_score__lte=100.0),
                name="check_external_rec_final_score_qualified_bounds",
            ),
            models.CheckConstraint(
                check=models.Q(semantic_score__gte=0.0) & models.Q(semantic_score__lte=100.0),
                name="check_external_rec_semantic_score_bounds",
            ),
            models.CheckConstraint(
                check=models.Q(skill_score__gte=0.0) & models.Q(skill_score__lte=100.0),
                name="check_external_rec_skill_score_bounds",
            ),
            models.CheckConstraint(
                check=models.Q(experience_score__gte=0.0) & models.Q(experience_score__lte=100.0),
                name="check_external_rec_experience_score_bounds",
            ),
        ]
        indexes = [
            models.Index(
                fields=["candidate_profile", "-final_score"],
                name="idx_ext_rec_cand_score",
            ),
            models.Index(
                fields=["calculated_at"],
                name="idx_ext_rec_calc_at",
            ),
        ]

    def clean(self):
        super().clean()
        if self.final_score is not None and self.final_score < 70.0:
            raise ValidationError(
                f"ExternalJobRecommendation only stores qualified recommendations with final_score >= 70.0 (got {self.final_score})."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        cand_email = self.candidate_profile.user.email if hasattr(self, 'candidate_profile') and self.candidate_profile else ''
        job_title = self.external_job.title if hasattr(self, 'external_job') and self.external_job else ''
        return f"ExternalJobRec ({self.final_score}%): {cand_email} -> {job_title}"


class ExternalJobRecommendationFeedback(models.Model):
    """
    Candidate-submitted feedback and issue reporting for AI-recommended external jobs.
    Phase 6Z.12B.

    Guarantees:
    - Associated strictly with the authenticated candidate profile.
    - References the specific recommendation and external job.
    - Captures structured reason categories and optional comment (max 1,000 chars).
    - Immutable feedback: does not alter recommendation scores, job status, or candidate eligibility.
    - Does not trigger external API calls.
    """
    class Reason(models.TextChoices):
        NOT_RELEVANT = "not_relevant", "Not relevant to my profile"
        EXPIRED_OR_UNAVAILABLE = "expired_unavailable", "Job appears expired or unavailable"
        BROKEN_LINK = "broken_link", "Application link is broken"
        INACCURATE_DETAILS = "inaccurate_details", "Job details appear inaccurate"
        INCORRECT_LOCATION = "incorrect_location", "Job location or remote status is incorrect"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate_profile = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="external_recommendation_feedback",
        help_text="Candidate who submitted the feedback.",
    )
    recommendation = models.ForeignKey(
        ExternalJobRecommendation,
        on_delete=models.CASCADE,
        related_name="feedback_reports",
        help_text="Recommendation being reported.",
    )
    external_job = models.ForeignKey(
        ExternalJob,
        on_delete=models.CASCADE,
        related_name="recommendation_feedback_reports",
        help_text="Underlying external job being reported.",
    )
    reason = models.CharField(
        max_length=40,
        choices=Reason.choices,
        db_index=True,
        help_text="Primary reason for reporting.",
    )
    comments = models.TextField(
        max_length=1000,
        blank=True,
        default="",
        help_text="Optional additional details or comments from candidate.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_job_recommendation_feedback"
        ordering = ["-created_at"]
        verbose_name = "External Job Recommendation Feedback"
        verbose_name_plural = "External Job Recommendation Feedback Reports"
        indexes = [
            models.Index(fields=["candidate_profile", "recommendation"], name="idx_rec_fb_cand_rec"),
            models.Index(fields=["reason"], name="idx_rec_fb_reason"),
            models.Index(fields=["created_at"], name="idx_rec_fb_created_at"),
        ]

    def clean(self):
        super().clean()
        if self.comments and len(self.comments.strip()) > 1000:
            raise ValidationError("Comments cannot exceed 1,000 characters.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Feedback ({self.reason}) by {self.candidate_profile_id} on Rec {self.recommendation_id}"
