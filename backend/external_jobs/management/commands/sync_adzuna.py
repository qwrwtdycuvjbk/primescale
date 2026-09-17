from django.core.management.base import BaseCommand
from external_jobs.providers.adzuna import sync_adzuna_jobs


class Command(BaseCommand):
    help = "Synchronizes public job advertisements from the official Adzuna API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--country",
            type=str,
            help="Target country code (e.g. us, gb). Defaults to ADZUNA_COUNTRY or 'us'.",
        )
        parser.add_argument(
            "--what",
            type=str,
            help="Search keywords/title filter (e.g. 'software engineer').",
        )
        parser.add_argument(
            "--location",
            type=str,
            help="Optional location string filter.",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            help="Maximum number of pages to fetch. Defaults to ADZUNA_MAX_PAGES or 3.",
        )
        parser.add_argument(
            "--results-per-page",
            type=int,
            help="Results per page. Defaults to ADZUNA_RESULTS_PER_PAGE or 20.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting Adzuna job synchronization..."))

        country = options.get("country")
        what = options.get("what")
        location = options.get("location")
        max_pages = options.get("max_pages")
        results_per_page = options.get("results_per_page")

        result = sync_adzuna_jobs(
            country=country,
            what=what,
            location=location,
            max_pages=max_pages,
            results_per_page=results_per_page,
        )

        if result.get("success"):
            self.stdout.write(self.style.SUCCESS("Adzuna sync completed"))
            self.stdout.write(f"Country: {result.get('country', 'us')}")
            queries = result.get("queries", [])
            self.stdout.write(f"Queries ({len(queries)}): {', '.join(queries)}")
            self.stdout.write(f"Pages: {result.get('pages_fetched', 0)}")
            self.stdout.write(f"Received: {result.get('jobs_received', 0)}")
            self.stdout.write(f"Created: {result.get('jobs_created', 0)}")
            self.stdout.write(f"Updated: {result.get('jobs_updated', 0)}")
            self.stdout.write(f"Inactive: {result.get('jobs_marked_inactive', 0)}")
            self.stdout.write(f"Duration: {result.get('duration_seconds', 0.0):.2f}s")
        else:
            self.stdout.write(self.style.ERROR("Adzuna sync failed"))
            self.stdout.write(f"Error: {result.get('error')}")
            self.stdout.write(f"Pages fetched before failure: {result.get('pages_fetched', 0)}")
            self.stdout.write(f"API errors encountered: {result.get('api_errors', 0)}")
