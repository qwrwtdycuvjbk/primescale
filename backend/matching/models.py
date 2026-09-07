import uuid
from django.db import models
from candidates.models import CandidateProfile
from jobs.models import Job


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
