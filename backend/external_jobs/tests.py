from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.db import IntegrityError
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from external_jobs.models import ExternalJob, ExternalJobSource
from external_jobs.utils import classify_remote_type, generate_dedup_hash
from external_jobs.providers.people_prime import (
    sync_people_prime_jobs,
    extract_country,
    PEOPLE_PRIME_PROVIDER_CODE,
)
from jobs.models import Job as InternalJob
from matching.models import Match as InternalMatch
from applications.models import Application as InternalApplication


class PeoplePrimeSyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_extract_country(self):
        self.assertEqual(extract_country("Hyderabad", "Telangana", "Pan India"), "IN")
        self.assertEqual(extract_country("Bengaluru", "Karnataka", "India"), "IN")
        self.assertEqual(extract_country("Austin", "TX", "US"), "US")
        self.assertEqual(extract_country(None, None, None), "UNKNOWN")

    def test_work_mode_classification(self):
        self.assertEqual(classify_remote_type(raw_remote_str="Remote"), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Hybrid"), ExternalJob.RemoteType.HYBRID)
        self.assertEqual(classify_remote_type(raw_remote_str="On-site"), ExternalJob.RemoteType.ONSITE)
        self.assertEqual(classify_remote_type(raw_remote_str="Work From Office"), ExternalJob.RemoteType.ONSITE)
        self.assertEqual(classify_remote_type(raw_remote_str="Work From Home"), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Unknown Mode"), ExternalJob.RemoteType.UNKNOWN)

    @patch("requests.Session.get")
    def test_people_prime_sync_single_page(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 101,
                    "job_code": "PPW - 101",
                    "position": "US Remote Fullstack Developer",
                    "technology": "React, Python",
                    "required_skills": ["React", "Python"],
                    "city": "Austin",
                    "state": "TX",
                    "location": "US",
                    "job_type": "Full-time",
                    "work_mode": "Remote",
                    "description": "Great remote job in the US",
                    "created_at": "2026-09-10T10:00:00Z",
                },
                {
                    "id": 102,
                    "job_code": "PPW - 102",
                    "position": "Hyderabad QA Engineer",
                    "technology": "Selenium",
                    "city": "Hyderabad",
                    "state": "Telangana",
                    "location": "Pan India",
                    "job_type": "Contract",
                    "work_mode": "On-site",
                    "description": "Onsite tester in India",
                    "created_at": "2026-09-10T10:00:00Z",
                },
            ],
        }
        mock_get.return_value = mock_response

        res = sync_people_prime_jobs()

        self.assertTrue(res["success"])
        self.assertEqual(res["jobs_received"], 2)
        self.assertEqual(res["jobs_created"], 2)

        # Verify job 101 (US Remote)
        j1 = ExternalJob.objects.get(external_job_id="101")
        self.assertEqual(j1.title, "US Remote Fullstack Developer")
        self.assertEqual(j1.country, "US")
        self.assertEqual(j1.remote_type, ExternalJob.RemoteType.REMOTE)
        self.assertEqual(j1.original_job_url, "https://people-prime.com/job-details?id=101")

        # Verify job 102 (India Onsite)
        j2 = ExternalJob.objects.get(external_job_id="102")
        self.assertEqual(j2.country, "IN")
        self.assertEqual(j2.remote_type, ExternalJob.RemoteType.ONSITE)

        # Verify frontend US Remote filter excludes Indian job
        api_res = self.client.get("/api/v1/external-jobs/?country=US&remote=true")
        self.assertEqual(api_res.status_code, status.HTTP_200_OK)
        data = api_res.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["external_job_id"], "101")

    @patch("requests.Session.get")
    def test_people_prime_pagination_multi_page(self, mock_get):
        page1 = MagicMock()
        page1.raise_for_status.return_value = None
        page1.json.return_value = {
            "count": 2,
            "next": "https://ats.people-prime.com/api/public/jobs/?page=2",
            "results": [
                {
                    "id": 201,
                    "job_code": "PPW - 200",
                    "position": "Job Page 1",
                    "city": "Austin",
                    "location": "US",
                    "work_mode": "Remote",
                    "description": "Desc 1",
                }
            ],
        }

        page2 = MagicMock()
        page2.raise_for_status.return_value = None
        page2.json.return_value = {
            "count": 2,
            "next": None,
            "results": [
                {
                    "id": 202,
                    "job_code": "PPW - 200",  # Same job_code, different external_job_id
                    "position": "Job Page 2",
                    "city": "Austin",
                    "location": "US",
                    "work_mode": "Remote",
                    "description": "Desc 2",
                }
            ],
        }

        mock_get.side_effect = [page1, page2]

        res = sync_people_prime_jobs()
        self.assertTrue(res["success"])
        self.assertEqual(res["pages_fetched"], 2)
        self.assertEqual(res["jobs_created"], 2)

        # Verify duplicate job_code with different IDs exist as separate records
        self.assertEqual(ExternalJob.objects.count(), 2)

    @patch("requests.Session.get")
    def test_idempotent_sync_and_updates(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "count": 1,
            "next": None,
            "results": [
                {
                    "id": 301,
                    "position": "Initial Title",
                    "description": "Initial Desc",
                    "city": "Austin",
                    "location": "US",
                    "work_mode": "Remote",
                }
            ],
        }
        mock_get.return_value = mock_response

        # Run 1: Create
        res1 = sync_people_prime_jobs()
        self.assertEqual(res1["jobs_created"], 1)

        # Update title in API response
        mock_response.json.return_value["results"][0]["position"] = "Updated Title"

        # Run 2: Update (Idempotent)
        res2 = sync_people_prime_jobs()
        self.assertEqual(res2["jobs_created"], 0)
        self.assertEqual(res2["jobs_updated"], 1)

        j = ExternalJob.objects.get(external_job_id="301")
        self.assertEqual(j.title, "Updated Title")

    @patch("requests.Session.get")
    def test_partial_sync_failure_safety(self, mock_get):
        # Create an existing job
        source = ExternalJobSource.objects.create(
            name="People Prime",
            provider_code="people_prime",
            api_enabled=True,
        )
        existing_job = ExternalJob.objects.create(
            source=source,
            external_job_id="old-job",
            title="Existing Job",
            company_name="People Prime",
            description="Desc",
            original_job_url="https://example.com/old",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        # Mock page 1 success, page 2 failure
        page1 = MagicMock()
        page1.raise_for_status.return_value = None
        page1.json.return_value = {
            "count": 2,
            "next": "https://ats.people-prime.com/api/public/jobs/?page=2",
            "results": [
                {
                    "id": 401,
                    "position": "New Job Page 1",
                    "description": "Desc",
                }
            ],
        }

        page2 = MagicMock()
        page2.raise_for_status.side_effect = Exception("HTTP 500 Internal Server Error")

        mock_get.side_effect = [page1, page2]

        res = sync_people_prime_jobs()

        self.assertFalse(res["success"])
        self.assertEqual(res["jobs_created"], 1)

        # PARTIAL SYNC SAFETY: Existing job must NOT be marked inactive due to mid-sync failure
        existing_job.refresh_from_db()
        self.assertTrue(existing_job.is_active)
        self.assertEqual(existing_job.status, ExternalJob.Status.ACTIVE)

    @patch("requests.Session.get")
    def test_stale_job_reconciliation_on_full_sync_success(self, mock_get):
        source = ExternalJobSource.objects.create(
            name="People Prime",
            provider_code="people_prime",
            api_enabled=True,
        )
        stale_job = ExternalJob.objects.create(
            source=source,
            external_job_id="stale-99",
            title="Stale Position",
            company_name="People Prime",
            description="Desc",
            original_job_url="https://example.com/stale",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        # Mock full successful sync returning only job 501
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "count": 1,
            "next": None,
            "results": [
                {
                    "id": 501,
                    "position": "Active Position",
                    "description": "Desc",
                }
            ],
        }
        mock_get.return_value = mock_response

        res = sync_people_prime_jobs()
        self.assertTrue(res["success"])
        self.assertEqual(res["jobs_marked_inactive"], 1)

        stale_job.refresh_from_db()
        self.assertFalse(stale_job.is_active)
        self.assertEqual(stale_job.status, ExternalJob.Status.INACTIVE)

    @patch("requests.Session.get")
    def test_no_internal_model_side_effects(self, mock_get):
        initial_job_count = InternalJob.objects.count()
        initial_app_count = InternalApplication.objects.count()
        initial_match_count = InternalMatch.objects.count()

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "count": 1,
            "next": None,
            "results": [
                {
                    "id": 601,
                    "position": "Test Isolation",
                    "description": "Desc",
                }
            ],
        }
        mock_get.return_value = mock_response

        sync_people_prime_jobs()

        self.assertEqual(InternalJob.objects.count(), initial_job_count)
        self.assertEqual(InternalApplication.objects.count(), initial_app_count)
        self.assertEqual(InternalMatch.objects.count(), initial_match_count)
