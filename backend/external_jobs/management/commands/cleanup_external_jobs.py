from django.core.management.base import BaseCommand
from external_jobs.cleanup import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_RETENTION_DAYS,
    ALLOWED_CLEANUP_PROVIDERS,
    cleanup_external_jobs,
)


class Command(BaseCommand):
    help = (
        "Cleans up stale third-party external job listings older than 21 days (posted_at). "
        "Defaults to dry-run mode. Requires --execute to delete records."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_RETENTION_DAYS,
            help=f"Retention window in days based on original posted_at date (default: {DEFAULT_RETENTION_DAYS}).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Batch size for deletion transactions (default: {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            default=False,
            help="Explicit confirmation required to perform physical database deletions. Default is dry-run.",
        )
        parser.add_argument(
            "--provider",
            type=str,
            default=None,
            help=f"Optionally target a specific provider from {ALLOWED_CLEANUP_PROVIDERS}.",
        )

    def handle(self, *args, **options):
        days = options.get("days", DEFAULT_RETENTION_DAYS)
        batch_size = options.get("batch_size", DEFAULT_BATCH_SIZE)
        execute = options.get("execute", False)
        provider_arg = options.get("provider")

        if provider_arg:
            target_providers = [provider_arg.strip().lower()]
        else:
            target_providers = list(ALLOWED_CLEANUP_PROVIDERS)

        mode_label = "EXECUTE (DELETION)" if execute else "DRY-RUN (AUDIT ONLY)"
        self.stdout.write(
            self.style.NOTICE(
                f"\n=== External Job Cleanup [{mode_label}] ===\n"
                f"Retention Cutoff: > {days} days old (posted_at)\n"
                f"Target Providers: {', '.join(target_providers)}\n"
                f"Batch Size: {batch_size}\n"
            )
        )

        results = cleanup_external_jobs(
            days=days,
            batch_size=batch_size,
            execute=execute,
            providers=target_providers,
        )

        self.stdout.write(f"Scanned total listings:   {results['scanned_count']}")
        self.stdout.write(f"Skipped fresh listings:   {results['skipped_fresh']}")
        self.stdout.write(
            self.style.WARNING(
                f"Skipped missing dates:    {results['skipped_missing_date']} (posted_at IS NULL, preserved conservatively)"
            )
        )
        self.stdout.write(
            self.style.NOTICE(
                f"Eligible for deletion:    {results['eligible_count']}"
            )
        )

        self.stdout.write("\n--- Eligible Jobs by Provider ---")
        for prov, count in results["eligible_by_provider"].items():
            self.stdout.write(f"  {prov:12}: {count}")

        self.stdout.write("\n--- Eligible Jobs by Age Bucket ---")
        for bucket, count in results["eligible_by_age_bucket"].items():
            self.stdout.write(f"  {bucket:16}: {count}")

        if execute:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully DELETED:     {results['deleted_count']} jobs across {results['batches_processed']} batch(es)."
                )
            )
            if results["failed_count"] > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"FAILED deletions:         {results['failed_count']} jobs encountered errors."
                    )
                )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nDRY-RUN COMPLETE: Zero database modifications were performed.\n"
                    "Pass '--execute' to permanently delete eligible listings."
                )
            )

        self.stdout.write(f"Duration: {results['duration_seconds']}s\n")
