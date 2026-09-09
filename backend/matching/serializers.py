from rest_framework import serializers
from candidates.models import CandidateProfile
from jobs.models import Job
from .models import Match


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
            "resume_url",
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
