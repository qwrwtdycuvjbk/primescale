import sys
from django.db import models
from django.core.management.base import BaseCommand
from django.utils import timezone
from external_jobs.models import ExternalJob
from matching.models import ExternalJobEmbedding, EmbeddingStatus
from matching.external_job_embeddings import (
    ExternalJobEmbeddingService,
    ExternalJobTextPreparationService,
)


class Command(BaseCommand):
    help = (
        "Generates dense 2,048-dimensional passage embeddings for eligible external jobs. "
        "Defaults strictly to dry-run mode. Requires --execute and a positive --limit to run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=True,
            help="Simulate execution without generating embeddings or calling APIs (default: True).",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            default=False,
            help="Explicit confirmation flag to execute embedding generation.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of external jobs to process (required when using --execute).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of records to process per batch (default: 50).",
        )
        parser.add_argument(
            "--provider",
            type=str,
            default=None,
            help="Filter by external job source provider_code (e.g. adzuna, himalayas).",
        )
        parser.add_argument(
            "--status",
            type=str,
            default=None,
            choices=["pending", "failed", "all"],
            help="Filter by embedding status: pending (missing or pending), failed, or all.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Force regeneration of embeddings even if content hash matches.",
        )

    def handle(self, *args, **options):
        is_execute = options.get("execute", False)
        is_dry_run = not is_execute or options.get("dry_run", True)
        limit = options.get("limit")
        batch_size = options.get("batch_size") or 50
        provider = options.get("provider")
        status_filter = options.get("status")
        force = options.get("force", False)

        self.stdout.write(self.style.MIGRATE_HEADING("=== External Job Embedding Generator ==="))

        if is_dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN MODE ACTIVE: No external API calls will be made, and no database changes will occur.\n"
                    "Pass '--execute --limit=<N>' to run embedding generation."
                )
            )
        else:
            if not limit or limit <= 0:
                self.stderr.write(
                    self.style.ERROR(
                        "Safety constraint: --limit must be provided with a positive integer when using --execute.\n"
                        "Example: python manage.py embed_external_jobs --execute --limit=10"
                    )
                )
                sys.exit(1)

        # 1. Base eligibility queryset
        now = timezone.now()
        base_qs = ExternalJob.objects.filter(
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
            country="US",
            remote_type__in=[ExternalJob.RemoteType.REMOTE, ExternalJob.RemoteType.HYBRID],
        ).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        ).select_related("source", "embedding_record")

        if provider:
            base_qs = base_qs.filter(source__provider_code__iexact=provider.strip())

        total_eligible = base_qs.count()

        # Embedded vs missing/pending
        embedded_count = base_qs.filter(
            embedding_record__isnull=False,
            embedding_record__status=EmbeddingStatus.COMPLETED,
            embedding_record__embedding__isnull=False,
        ).count()
        failed_count = base_qs.filter(
            embedding_record__isnull=False,
            embedding_record__status=EmbeddingStatus.FAILED,
        ).count()
        missing_count = total_eligible - embedded_count

        self.stdout.write(f"Total Eligible US Remote Jobs : {total_eligible}")
        self.stdout.write(f"Already Embedded (Completed)   : {embedded_count}")
        self.stdout.write(f"Failed Embedding Status        : {failed_count}")
        self.stdout.write(f"Missing / Unprocessed Jobs     : {missing_count}\n")

        # 2. Filter target queryset according to options
        target_qs = base_qs
        if status_filter == "pending":
            target_qs = target_qs.filter(
                models.Q(embedding_record__isnull=True)
                | models.Q(embedding_record__status=EmbeddingStatus.PENDING)
                | models.Q(embedding_record__embedding__isnull=True)
            )
        elif status_filter == "failed":
            target_qs = target_qs.filter(
                embedding_record__isnull=False,
                embedding_record__status=EmbeddingStatus.FAILED,
            )
        elif not force and status_filter != "all":
            # Default: process jobs needing embeddings
            target_qs = target_qs.filter(
                models.Q(embedding_record__isnull=True)
                | models.Q(embedding_record__status__in=[EmbeddingStatus.PENDING, EmbeddingStatus.FAILED])
                | models.Q(embedding_record__embedding__isnull=True)
            )

        target_total = target_qs.count()
        self.stdout.write(f"Jobs Matching Selection Criteria: {target_total}")

        if is_dry_run:
            sample_jobs = list(target_qs[:min(5, target_total)])
            if sample_jobs:
                self.stdout.write("\nSample eligible jobs to be processed:")
                for idx, sj in enumerate(sample_jobs, start=1):
                    prep = ExternalJobTextPreparationService.prepare_text(sj)
                    self.stdout.write(
                        f"  {idx}. [{sj.source.provider_code}] {sj.title} at {sj.company_name} "
                        f"(Hash: {prep.content_hash[:8]}, Chars: {prep.character_count})"
                    )
            self.stdout.write(self.style.SUCCESS("\nDry-run completed successfully. Zero API calls made."))
            return

        # 3. Execution Mode
        to_process = min(target_total, limit)
        self.stdout.write(self.style.NOTICE(f"\nBeginning execution for up to {to_process} external jobs..."))

        jobs_to_embed = list(target_qs[:to_process])
        service = ExternalJobEmbeddingService()

        completed_count = 0
        skipped_count = 0
        execution_failed_count = 0

        for job in jobs_to_embed:
            res = service.generate_embedding_for_job(job, force_regenerate=force, raise_on_transient=False)
            if res.status == EmbeddingStatus.COMPLETED:
                if res.is_unchanged:
                    skipped_count += 1
                else:
                    completed_count += 1
            else:
                execution_failed_count += 1
                self.stderr.write(f"Job {job.id} failed: {res.error_message}")

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Execution Summary ==="))
        self.stdout.write(f"Processed      : {len(jobs_to_embed)}")
        self.stdout.write(self.style.SUCCESS(f"New Embeddings : {completed_count}"))
        self.stdout.write(f"Skipped        : {skipped_count}")
        if execution_failed_count > 0:
            self.stdout.write(self.style.ERROR(f"Failed         : {execution_failed_count}"))
        else:
            self.stdout.write(f"Failed         : 0")
