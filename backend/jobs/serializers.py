from rest_framework import serializers
from companies.models import Company
from companies.serializers import CompanyPublicSerializer
from .models import Job
from .utils import default_job_expiry, is_valid_salary_range, parse_skills


class JobCompanySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name", "website", "logo_url", "hq_city", "country")


class JobSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(source="company.id", read_only=True)
    company_details = JobCompanySummarySerializer(source="company", read_only=True)
    companies = JobCompanySummarySerializer(source="company", read_only=True)
    posted_by_email = serializers.EmailField(source="posted_by.email", read_only=True)
    posted_by_full_name = serializers.CharField(source="posted_by.full_name", read_only=True)

    class Meta:
        model = Job
        fields = (
            "id",
            "company",
            "company_id",
            "company_details",
            "companies",
            "posted_by",
            "posted_by_email",
            "posted_by_full_name",
            "title",
            "description",
            "role_type",
            "experience_level",
            "tech_stack",
            "salary_range",
            "work_type",
            "visa_requirements",
            "status",
            "expires_at",
            "jd_quality_score",
            "jd_quality_feedback",
            "featured",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "posted_by",
            "expires_at",
            "created_at",
            "updated_at",
        )


class JobPublicListSerializer(serializers.ModelSerializer):
    company_details = JobCompanySummarySerializer(source="company", read_only=True)

    class Meta:
        model = Job
        fields = (
            "id",
            "title",
            "company_details",
            "role_type",
            "experience_level",
            "tech_stack",
            "salary_range",
            "work_type",
            "visa_requirements",
            "status",
            "featured",
            "created_at",
        )


class JobCreateUpdateSerializer(serializers.Serializer):
    company_id = serializers.UUIDField(required=False)
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    role_type = serializers.ChoiceField(choices=Job.RoleType.choices)
    experience_level = serializers.ChoiceField(choices=Job.ExperienceLevel.choices)
    tech_stack = serializers.JSONField(required=False)

    salary_range = serializers.CharField(max_length=100)
    work_type = serializers.CharField(max_length=50, required=False, default="remote")
    visa_requirements = serializers.CharField(required=False, allow_blank=True, default="")
    publish = serializers.BooleanField(required=False, default=False)
    status = serializers.ChoiceField(choices=Job.Status.choices, required=False)
    jd_quality_score = serializers.IntegerField(required=False, allow_null=True)
    jd_quality_feedback = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    featured = serializers.BooleanField(required=False, default=False)

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Job title is required.")
        return value.strip()

    def validate_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Description is required.")
        return value.strip()

    def validate_salary_range(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Salary range is required.")
        if not is_valid_salary_range(value):
            raise serializers.ValidationError(
                'Provide a real salary range. Phrases like "Competitive" or "DOE" are not allowed.'
            )
        return value.strip()

    def validate_tech_stack(self, value):
        parsed = parse_skills(value)
        if len(parsed) < 3:
            raise serializers.ValidationError("At least 3 skills are required in tech stack.")
        return parsed

    def validate_visa_requirements(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Describe who can work remotely in the US for this role."
            )
        return value.strip()
