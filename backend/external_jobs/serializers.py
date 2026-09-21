from rest_framework import serializers
from external_jobs.models import ExternalJob, ExternalJobSource
from external_jobs.utils import classify_job_department, html_to_plain_text


class ExternalJobSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalJobSource
        fields = [
            "id",
            "name",
            "provider_code",
            "attribution_name",
            "attribution_url",
        ]


class ExternalJobSerializer(serializers.ModelSerializer):
    source_attribution = ExternalJobSourceSerializer(source="source", read_only=True)
    department = serializers.SerializerMethodField()
    company_logo = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = ExternalJob
        fields = [
            "id",
            "external_job_id",
            "title",
            "company_name",
            "company_website",
            "company_logo",
            "description",
            "location",
            "country",
            "state",
            "city",
            "remote_type",
            "employment_type",
            "department",
            "salary_min",
            "salary_max",
            "salary_currency",
            "tech_stack",
            "original_job_url",
            "source_job_url",
            "source_name",
            "source_attribution",
            "posted_at",
            "expires_at",
            "status",
            "is_active",
            "created_at",
        ]

    def get_department(self, obj) -> str:
        return classify_job_department(
            title=obj.title,
            tech_stack=obj.tech_stack,
            description=obj.description,
        )

    def get_description(self, obj) -> str:
        return html_to_plain_text(obj.description)

    def get_company_logo(self, obj) -> str | None:
        if not isinstance(obj.raw_metadata, dict):
            return None
        logo = obj.raw_metadata.get("company_logo") or obj.raw_metadata.get("company_logo_url")
        if isinstance(logo, str):
            logo_str = logo.strip()
            if logo_str.startswith("http://") or logo_str.startswith("https://"):
                return logo_str
        return None
