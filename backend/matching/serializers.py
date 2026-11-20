from rest_framework import serializers
from candidates.models import CandidateProfile
from external_jobs.models import ExternalJob
from jobs.models import Job
from .models import Match, ExternalJobRecommendation, ExternalJobRecommendationFeedback


class CandidateJobSummarySerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_logo_url = serializers.CharField(source="company.logo_url", read_only=True)
    companies = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = (
            "id",
            "title",
            "description",
            "tech_stack",
            "salary_range",
            "experience_level",
            "role_type",
            "work_type",
            "visa_requirements",
            "posted_by",
            "company_name",
            "company_logo_url",
            "companies",
        )

    def get_companies(self, obj):
        if not obj.company:
            return None
        return {
            "name": obj.company.name,
            "logo_url": obj.company.logo_url,
        }


class CandidateMatchSerializer(serializers.ModelSerializer):
    job = CandidateJobSummarySerializer(read_only=True)
    jobs = CandidateJobSummarySerializer(source="job", read_only=True)

    class Meta:
        model = Match
        fields = (
            "id",
            "job",
            "jobs",
            "match_score",
            "match_reason",
            "status",
            "created_at",
            "updated_at",
        )


class EmployerCandidateProfileSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    profiles = serializers.SerializerMethodField()

    class Meta:
        model = CandidateProfile
        fields = (
            "id",
            "full_name",
            "email",
            "profiles",
            "headline",
            "current_title",
            "years_experience",
            "skills",
            "experience_level",
            "work_authorization",
            "us_state",
            "remote_preference",
            "linkedin_url",
            "github_url",
            "portfolio_url",
        )

    def get_profiles(self, obj):
        if not obj.user:
            return None
        return {
            "full_name": obj.user.full_name,
            "email": obj.user.email,
            "phone": obj.phone or getattr(obj.user, "phone", None),
        }


class EmployerMatchSerializer(serializers.ModelSerializer):
    candidate_profile = EmployerCandidateProfileSummarySerializer(read_only=True)
    candidate_profiles = EmployerCandidateProfileSummarySerializer(source="candidate_profile", read_only=True)
    job = CandidateJobSummarySerializer(read_only=True)
    jobs = CandidateJobSummarySerializer(source="job", read_only=True)
    job_id = serializers.UUIDField(source="job.id", read_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)

    class Meta:
        model = Match
        fields = (
            "id",
            "job_id",
            "job_title",
            "job",
            "jobs",
            "candidate_profile",
            "candidate_profiles",
            "match_score",
            "match_reason",
            "status",
            "visible_to_employer",
            "created_at",
            "updated_at",
        )


class AdminMatchSerializer(serializers.ModelSerializer):
    candidate_profile = EmployerCandidateProfileSummarySerializer(read_only=True)
    candidate_profiles = EmployerCandidateProfileSummarySerializer(source="candidate_profile", read_only=True)
    job = CandidateJobSummarySerializer(read_only=True)
    jobs = CandidateJobSummarySerializer(source="job", read_only=True)

    class Meta:
        model = Match
        fields = (
            "id",
            "candidate_profile",
            "candidate_profiles",
            "job",
            "jobs",
            "match_score",
            "match_reason",
            "status",
            "visible_to_employer",
            "recruiter_notified_at",
            "created_at",
            "updated_at",
        )


class MatchStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            (Match.Status.CANDIDATE_INTERESTED, "Candidate Interested"),
            (Match.Status.EMPLOYER_SHORTLISTED, "Employer Shortlisted"),
            (Match.Status.REJECTED, "Rejected"),
        ]
    )


class AdminMatchActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])


class CandidateExternalJobSummarySerializer(serializers.ModelSerializer):
    """
    Public-safe representation of an external job for candidate recommendations.
    Never exposes raw internal embeddings, error logs, or candidate resume URLs.
    Includes sanitized application URLs and provider attribution.
    """
    job_title = serializers.CharField(source="title", read_only=True)
    source_attribution = serializers.SerializerMethodField()
    application_url = serializers.SerializerMethodField()

    class Meta:
        model = ExternalJob
        fields = (
            "id",
            "external_job_id",
            "job_title",
            "company_name",
            "company_website",
            "location",
            "country",
            "state",
            "city",
            "remote_type",
            "employment_type",
            "salary_min",
            "salary_max",
            "salary_currency",
            "tech_stack",
            "source_name",
            "source_attribution",
            "posted_at",
            "expires_at",
            "original_job_url",
            "source_job_url",
            "application_url",
        )

    def _is_valid_http_url(self, url: str | None) -> bool:
        if not url or not isinstance(url, str):
            return False
        url_lower = url.strip().lower()
        return url_lower.startswith("http://") or url_lower.startswith("https://")

    def get_application_url(self, obj: ExternalJob) -> str | None:
        """
        Returns the direct application URL: prefers original_job_url if valid HTTP/HTTPS,
        falling back to source_job_url.
        """
        if self._is_valid_http_url(obj.original_job_url):
            return obj.original_job_url.strip()
        if self._is_valid_http_url(obj.source_job_url):
            return obj.source_job_url.strip()
        return None

    def get_source_attribution(self, obj: ExternalJob) -> dict | None:
        if not obj.source:
            return None
        return {
            "name": obj.source.name,
            "provider_code": obj.source.provider_code,
            "attribution_name": obj.source.attribution_name,
            "attribution_url": obj.source.attribution_url,
        }


class CandidateExternalJobRecommendationSerializer(serializers.ModelSerializer):
    """
    Candidate-safe recommendation serializer.
    Combines hybrid recommendation scores and external job metadata.
    Excludes internal embeddings, prompt texts, and private candidate details.
    """
    recommendation_id = serializers.UUIDField(source="id", read_only=True)
    external_job = CandidateExternalJobSummarySerializer(read_only=True)

    class Meta:
        from .models import ExternalJobRecommendation

        model = ExternalJobRecommendation
        fields = (
            "recommendation_id",
            "final_score",
            "semantic_score",
            "skill_score",
            "experience_score",
            "matched_skills",
            "match_reason",
            "calculated_at",
            "external_job",
        )


class ExternalJobRecommendationFeedbackCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for candidate feedback submission on external job recommendations.
    Phase 6Z.12B.
    """
    recommendation_id = serializers.UUIDField(write_only=True)
    reason = serializers.ChoiceField(choices=ExternalJobRecommendationFeedback.Reason.choices)
    comments = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )

    class Meta:
        model = ExternalJobRecommendationFeedback
        fields = (
            "id",
            "recommendation_id",
            "reason",
            "comments",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate_comments(self, value):
        if value and len(value) > 1000:
            raise serializers.ValidationError("Comments cannot exceed 1,000 characters.")
        return value
