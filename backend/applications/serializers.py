"""
Serializers for Job Applications.
Phase 17 — Job Applications Migration.
"""

from rest_framework import serializers
from matching.models import Match
from matching.serializers import (
    CandidateJobSummarySerializer,
    EmployerCandidateProfileSummarySerializer,
)
from jobs.models import Job


class ApplicationSerializer(serializers.ModelSerializer):
    """
    Serializes an Application (backed by Match) with shape compatibility
    for candidate and employer views.
    """
    job = CandidateJobSummarySerializer(read_only=True)
    jobs = CandidateJobSummarySerializer(source="job", read_only=True)
    candidate_profile = EmployerCandidateProfileSummarySerializer(read_only=True)
    candidate_profiles = EmployerCandidateProfileSummarySerializer(source="candidate_profile", read_only=True)
    applied_at = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = Match
        fields = [
            "id",
            "job",
            "jobs",
            "candidate_profile",
            "candidate_profiles",
            "match_score",
            "match_reason",
            "status",
            "visible_to_employer",
            "applied_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "match_score",
            "match_reason",
            "applied_at",
            "created_at",
            "updated_at",
        ]


class ApplyToJobSerializer(serializers.Serializer):
    """
    Validates a candidate applying to an active job.
    """
    job_id = serializers.UUIDField(required=True)
    cover_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_job_id(self, value):
        job = Job.objects.filter(id=value).first()
        if not job:
            raise serializers.ValidationError("Job not found.")
        if job.status != Job.Status.ACTIVE:
            raise serializers.ValidationError(f"Cannot apply to job with status '{job.status}'. Only active jobs accept applications.")
        return value


class ApplicationStatusUpdateSerializer(serializers.Serializer):
    """
    Validates application status transitions.
    """
    status = serializers.ChoiceField(
        choices=[
            Match.Status.CANDIDATE_INTERESTED,
            Match.Status.EMPLOYER_SHORTLISTED,
            Match.Status.MUTUAL_FIT,
            Match.Status.REJECTED,
        ]
    )
    notes = serializers.CharField(required=False, allow_blank=True)
