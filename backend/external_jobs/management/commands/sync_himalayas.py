from django.core.management.base import BaseCommand
from external_jobs.providers.himalayas import sync_himalayas_jobs


class Command(BaseCommand):
    help = "Synchronizes public remote job listings from the Himalayas Remote Jobs API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-pages",
            type=int,
            default=None,
            help="Maximum number of pages to fetch (20 jobs per page). Defaults to all pages.",
        )
        parser.add_argument(
            "--page-size",
            type=int,
            default=20,
            help="Jobs per page (max 20 per Himalayas API specification).",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting Himalayas remote job synchronization..."))

        max_pages = options.get("max_pages")
        page_size = options.get("page_size", 20)

        result = sync_himalayas_jobs(
            max_pages=max_pages,
            page_size=page_size,
        )

        if result.get("success"):
            self.stdout.write(self.style.SUCCESS("Himalayas sync completed successfully!"))
            self.stdout.write(f"Pages fetched: {result.get('pages_fetched', 0)}")
            self.stdout.write(f"Jobs received: {result.get('jobs_received', 0)}")
            self.stdout.write(f"Jobs created: {result.get('jobs_created', 0)}")
            self.stdout.write(f"Jobs updated: {result.get('jobs_updated', 0)}")
            self.stdout.write(f"Jobs marked inactive: {result.get('jobs_marked_inactive', 0)}")
            self.stdout.write(f"Active jobs in database: {result.get('active_jobs_count', 0)}")
            self.stdout.write(f"Duration: {result.get('duration_seconds', 0.0):.2f}s")
        else:
            self.stdout.write(self.style.ERROR("Himalayas sync failed!"))
            self.stdout.write(f"Error: {result.get('error')}")
            self.stdout.write(f"Pages fetched before failure: {result.get('pages_fetched', 0)}")
            self.stdout.write(f"API errors: {result.get('api_errors', 0)}")
