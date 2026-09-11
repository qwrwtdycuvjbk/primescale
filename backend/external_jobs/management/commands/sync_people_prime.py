from django.core.management.base import BaseCommand
from external_jobs.providers.people_prime import sync_people_prime_jobs


class Command(BaseCommand):
    help = "Manually triggers external public job synchronization from People Prime ATS API."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting People Prime ATS job sync..."))
        result = sync_people_prime_jobs()

        if result.get("success"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sync Successful! Pages: {result['pages_fetched']}, "
                    f"Received: {result['jobs_received']}, Created: {result['jobs_created']}, "
                    f"Updated: {result['jobs_updated']}, Inactive: {result['jobs_marked_inactive']}, "
                    f"Duration: {result['duration_seconds']:.2f}s"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"Sync Failed! Error: {result.get('error')}, "
                    f"Pages fetched before error: {result['pages_fetched']}"
                )
            )
