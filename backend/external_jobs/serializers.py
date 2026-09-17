from rest_framework import serializers
from external_jobs.models import ExternalJob, ExternalJobSource
from external_jobs.utils import classify_job_department


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

    class Meta:
        model = ExternalJob
        fields = [
            "id",
            "external_job_id",
            "title",
            "company_name",
            "company_website",
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
