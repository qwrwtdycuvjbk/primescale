from rest_framework import serializers
from .models import JobLead, RoleSubmission


class JobLeadSerializer(serializers.ModelSerializer):
    companyWebsite = serializers.CharField(source="company_website", allow_null=True, required=False)
    applyUrl = serializers.CharField(source="apply_url", allow_null=True, required=False)
    postedAt = serializers.CharField(source="posted_at", allow_null=True, required=False)
    employmentType = serializers.CharField(source="employment_type", allow_null=True, required=False)
    isRemote = serializers.BooleanField(source="is_remote", default=True)
    descriptionPreview = serializers.CharField(source="description_preview", allow_null=True, required=False)
    sourceLocale = serializers.CharField(source="source_locale", allow_null=True, required=False)

    class Meta:
        model = JobLead
        fields = [
            "id",
            "external_id",
            "title",
            "company",
            "companyWebsite",
            "applyUrl",
            "publisher",
            "postedAt",
            "country",
            "location",
            "employmentType",
            "isRemote",
            "descriptionPreview",
            "sourceLocale",
            "created_at",
        ]


class RoleSubmissionSerializer(serializers.ModelSerializer):
    companyName = serializers.CharField(source="company_name", required=False)
    contactName = serializers.CharField(source="contact_name", required=False)
    jobTitle = serializers.CharField(source="job_title", required=False)
    roleType = serializers.CharField(source="role_type", required=False)
    experienceLevel = serializers.CharField(source="experience_level", required=False)
    techStack = serializers.CharField(source="tech_stack", required=False)
    salaryRange = serializers.CharField(source="salary_range", required=False, allow_null=True, allow_blank=True)
    submissionType = serializers.CharField(source="submission_type", required=False, default="manual_form")

    class Meta:
        model = RoleSubmission
        fields = [
            "id",
            "created_at",
            "company_name",
            "companyName",
            "contact_name",
            "contactName",
            "email",
            "phone",
            "job_title",
            "jobTitle",
            "role_type",
            "roleType",
            "experience_level",
            "experienceLevel",
            "tech_stack",
            "techStack",
            "salary_range",
            "salaryRange",
            "description",
            "notes",
            "submission_type",
            "submissionType",
        ]
        extra_kwargs = {
            "company_name": {"required": False},
            "contact_name": {"required": False},
            "job_title": {"required": False},
            "role_type": {"required": False},
            "experience_level": {"required": False},
            "tech_stack": {"required": False},
        }

    def validate(self, attrs):
        # Normalize email
        if "email" in attrs:
            attrs["email"] = attrs["email"].strip().lower()

        # Ensure required logical fields exist whether passed in camelCase or snake_case
        required_fields = [
            ("company_name", "Company name is required"),
            ("contact_name", "Contact name is required"),
            ("email", "Valid email is required"),
            ("phone", "Phone number is required"),
            ("job_title", "Job title is required"),
            ("role_type", "Role type is required"),
            ("experience_level", "Experience level is required"),
            ("tech_stack", "Tech stack is required"),
            ("description", "Description is required"),
        ]

        for field, err in required_fields:
            val = attrs.get(field)
            if not val or not str(val).strip():
                raise serializers.ValidationError({field: err})

        return attrs
