from django.apps import AppConfig


class ExternalJobsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "external_jobs"
    verbose_name = "External Job Aggregation"
