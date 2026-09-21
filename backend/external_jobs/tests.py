import requests
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.db import IntegrityError
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from external_jobs.models import ExternalJob, ExternalJobSource
from external_jobs.utils import (
    classify_remote_type,
    generate_dedup_hash,
    clean_html_text,
    html_to_plain_text,
)
from external_jobs.providers.people_prime import (
    sync_people_prime_jobs,
    extract_country,
    PEOPLE_PRIME_PROVIDER_CODE,
)
from external_jobs.providers.adzuna import (
    sync_adzuna_jobs,
    ADZUNA_PROVIDER_CODE,
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
        # Existing and core remote indicators
        self.assertEqual(classify_remote_type(raw_remote_str="Remote"), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Fully Remote"), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="100% Remote"), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Work From Home"), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="work-from-home"), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="work from anywhere"), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="WFH"), ExternalJob.RemoteType.REMOTE)

        # Extended remote terminology
        self.assertEqual(classify_remote_type(raw_remote_str="This position is open to telecommuter candidates."), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Telecommuting eligible role."), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Telework options available."), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Option for teleworking."), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Candidates may work remotely."), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Exciting remote role in fintech."), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Remote opportunity for senior engineers."), ExternalJob.RemoteType.REMOTE)
        self.assertEqual(classify_remote_type(raw_remote_str="Remote position available."), ExternalJob.RemoteType.REMOTE)

        # Hybrid indicators
        self.assertEqual(classify_remote_type(raw_remote_str="Hybrid"), ExternalJob.RemoteType.HYBRID)
        self.assertEqual(classify_remote_type(raw_remote_str="Partially remote with 2 days in office."), ExternalJob.RemoteType.HYBRID)
        self.assertEqual(classify_remote_type(raw_remote_str="Flexible remote schedule."), ExternalJob.RemoteType.HYBRID)

        # Onsite indicators
        self.assertEqual(classify_remote_type(raw_remote_str="On-site"), ExternalJob.RemoteType.ONSITE)
        self.assertEqual(classify_remote_type(raw_remote_str="Work From Office"), ExternalJob.RemoteType.ONSITE)
        self.assertEqual(classify_remote_type(raw_remote_str="Must work in-office 5 days a week."), ExternalJob.RemoteType.ONSITE)

        # Conservative fallback to UNKNOWN when no explicit work-mode given
        self.assertEqual(classify_remote_type(location_str="Austin, TX", raw_remote_str="Software Engineer needed"), ExternalJob.RemoteType.UNKNOWN)
        self.assertEqual(classify_remote_type(location_str="United States", raw_remote_str="General Description"), ExternalJob.RemoteType.UNKNOWN)
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


class AdzunaSyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("requests.Session.get")
    def test_adzuna_sync_single_page_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "count": 2,
            "results": [
                {
                    "id": "9001",
                    "title": "Senior Python Developer",
                    "description": "We are seeking a <strong>Remote</strong> Python developer.",
                    "redirect_url": "https://www.adzuna.com/land/ad/9001?se=abc",
                    "created": "2026-09-12T10:00:00Z",
                    "company": {"display_name": "Apex Innovations"},
                    "location": {
                        "display_name": "San Francisco, CA",
                        "area": ["US", "California", "San Francisco County", "San Francisco"],
                    },
                    "category": {"label": "IT Jobs", "tag": "it-jobs"},
                    "salary_min": 140000.0,
                    "salary_max": 180000.0,
                    "contract_type": "permanent",
                    "contract_time": "full_time",
                },
                {
                    "id": "9002",
                    "title": "Onsite Infrastructure Engineer",
                    "description": "Work from office in Chicago, IL.",
                    "redirect_url": "https://www.adzuna.com/land/ad/9002?se=xyz",
                    "created": "2026-09-12T11:00:00Z",
                    "company": {"display_name": "Midwest Systems"},
                    "location": {
                        "display_name": "Chicago, IL",
                        "area": ["US", "Illinois", "Cook County", "Chicago"],
                    },
                    "category": {"label": "Engineering Jobs", "tag": "engineering-jobs"},
                    "salary_min": 110000.0,
                    "salary_max": 130000.0,
                    "contract_type": "contract",
                    "contract_time": "full_time",
                },
            ],
        }
        mock_get.return_value = mock_response

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(country="us", what="software developer", max_pages=1)

        self.assertTrue(res["success"])
        self.assertEqual(res["provider"], "adzuna")
        self.assertEqual(res["jobs_received"], 2)
        self.assertEqual(res["jobs_created"], 2)

        # Check job 9001 (Remote)
        j1 = ExternalJob.objects.get(external_job_id="9001")
        self.assertEqual(j1.title, "Senior Python Developer")
        self.assertEqual(j1.company_name, "Apex Innovations")
        self.assertEqual(j1.country, "US")
        self.assertEqual(j1.remote_type, ExternalJob.RemoteType.REMOTE)
        self.assertEqual(j1.original_job_url, "https://www.adzuna.com/land/ad/9001?se=abc")
        self.assertEqual(float(j1.salary_min), 140000.0)
        self.assertEqual(float(j1.salary_max), 180000.0)
        self.assertEqual(j1.employment_type, "Full Time Permanent")
        self.assertEqual(j1.source_name, "Adzuna")
        self.assertIn("IT Jobs", j1.tech_stack)
        self.assertNotIn("<strong>", j1.description)

        # Check job 9002 (Onsite)
        j2 = ExternalJob.objects.get(external_job_id="9002")
        self.assertEqual(j2.remote_type, ExternalJob.RemoteType.ONSITE)
        self.assertEqual(j2.employment_type, "Full Time Contract")

        # Test querying endpoint with source=adzuna
        api_res = self.client.get("/api/v1/external-jobs/?source=adzuna")
        self.assertEqual(api_res.status_code, status.HTTP_200_OK)
        data = api_res.json()
        self.assertEqual(data["count"], 2)

    @patch("requests.Session.get")
    def test_adzuna_pagination_multi_page(self, mock_get):
        page1 = MagicMock()
        page1.raise_for_status.return_value = None
        page1.json.return_value = {
            "count": 2,
            "results": [
                {
                    "id": "8001",
                    "title": "Adzuna Page 1 Role",
                    "description": "Desc 1",
                    "redirect_url": "https://example.com/adzuna/8001",
                }
            ],
        }

        page2 = MagicMock()
        page2.raise_for_status.return_value = None
        page2.json.return_value = {
            "count": 2,
            "results": [
                {
                    "id": "8002",
                    "title": "Adzuna Page 2 Role",
                    "description": "Desc 2",
                    "redirect_url": "https://example.com/adzuna/8002",
                }
            ],
        }

        mock_get.side_effect = [page1, page2]

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(country="us", what="software developer", max_pages=2, results_per_page=1)

        self.assertTrue(res["success"])
        self.assertEqual(res["pages_fetched"], 2)
        self.assertEqual(res["jobs_created"], 2)
        self.assertEqual(ExternalJob.objects.filter(source__provider_code="adzuna").count(), 2)

    @patch("requests.Session.get")
    def test_adzuna_empty_results(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"count": 0, "results": []}
        mock_get.return_value = mock_response

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(country="us", what="software developer", max_pages=3)

        self.assertTrue(res["success"])
        self.assertEqual(res["pages_fetched"], 1)
        self.assertEqual(res["jobs_received"], 0)
        self.assertEqual(res["jobs_created"], 0)

    def test_adzuna_missing_credentials(self):
        with patch("django.conf.settings.ADZUNA_APP_ID", ""), \
             patch("django.conf.settings.ADZUNA_APP_KEY", ""), \
             patch.dict("os.environ", {"ADZUNA_APP_ID": "", "ADZUNA_APP_KEY": ""}):
            res = sync_adzuna_jobs(what="software developer")

        self.assertFalse(res["success"])
        self.assertEqual(res["api_errors"], 1)
        self.assertIn("not configured", res["error"])

    @patch("requests.Session.get")
    def test_adzuna_api_error_response_500(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(what="software developer")

        self.assertFalse(res["success"])
        self.assertEqual(res["api_errors"], 1)

    @patch("requests.Session.get")
    def test_adzuna_network_connection_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Connection timed out")

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(what="software developer")

        self.assertFalse(res["success"])
        self.assertEqual(res["api_errors"], 1)

    @patch("requests.Session.get")
    def test_adzuna_idempotent_sync_and_updates(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "count": 1,
            "results": [
                {
                    "id": "7001",
                    "title": "Initial Adzuna Role",
                    "description": "Initial Desc",
                    "redirect_url": "https://example.com/adzuna/7001",
                }
            ],
        }
        mock_get.return_value = mock_response

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            # Run 1: Create
            res1 = sync_adzuna_jobs(what="software developer", max_pages=1)
            self.assertEqual(res1["jobs_created"], 1)
            self.assertEqual(res1["jobs_updated"], 0)

            # Update title in API response
            mock_response.json.return_value["results"][0]["title"] = "Updated Adzuna Role"

            # Run 2: Update (Idempotent, no duplicates)
            res2 = sync_adzuna_jobs(what="software developer", max_pages=1)
            self.assertEqual(res2["jobs_created"], 0)
            self.assertEqual(res2["jobs_updated"], 1)

        job = ExternalJob.objects.get(external_job_id="7001")
        self.assertEqual(job.title, "Updated Adzuna Role")

    @patch("requests.Session.get")
    def test_adzuna_partial_sync_failure_safety(self, mock_get):
        source = ExternalJobSource.objects.create(
            name="Adzuna",
            provider_code="adzuna",
            api_enabled=True,
        )
        existing_job = ExternalJob.objects.create(
            source=source,
            external_job_id="adzuna-old",
            title="Existing Adzuna Job",
            company_name="Adzuna Employer",
            description="Desc",
            original_job_url="https://example.com/adzuna-old",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        page1 = MagicMock()
        page1.raise_for_status.return_value = None
        page1.json.return_value = {
            "count": 2,
            "results": [
                {
                    "id": "6001",
                    "title": "Page 1 Adzuna Job",
                    "description": "Desc",
                    "redirect_url": "https://example.com/6001",
                }
            ],
        }

        page2 = MagicMock()
        page2.raise_for_status.side_effect = requests.HTTPError("502 Bad Gateway")

        mock_get.side_effect = [page1, page2]

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(what="software developer", max_pages=2, results_per_page=1)

        self.assertFalse(res["success"])
        # PARTIAL SYNC SAFETY: Existing job must NOT be expired/inactivated on mid-sync failure
        existing_job.refresh_from_db()
        self.assertTrue(existing_job.is_active)
        self.assertEqual(existing_job.status, ExternalJob.Status.ACTIVE)

    @patch("requests.Session.get")
    def test_adzuna_stale_job_reconciliation_on_full_sync_success(self, mock_get):
        source = ExternalJobSource.objects.create(
            name="Adzuna",
            provider_code="adzuna",
            api_enabled=True,
        )
        stale_job = ExternalJob.objects.create(
            source=source,
            external_job_id="adzuna-stale-99",
            title="Stale Position",
            company_name="Adzuna Employer",
            description="Desc",
            original_job_url="https://example.com/stale",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "count": 1,
            "results": [
                {
                    "id": "5001",
                    "title": "Active Position",
                    "description": "Desc",
                    "redirect_url": "https://example.com/5001",
                }
            ],
        }
        mock_get.return_value = mock_response

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(what="software developer", max_pages=1)

        self.assertTrue(res["success"])
        self.assertEqual(res["jobs_marked_inactive"], 1)

        stale_job.refresh_from_db()
        self.assertFalse(stale_job.is_active)
        self.assertEqual(stale_job.status, ExternalJob.Status.INACTIVE)

    def test_adzuna_credential_secrecy(self):
        secret_key = "very_secret_adzuna_key_12345"
        with patch("django.conf.settings.ADZUNA_APP_ID", "my_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", secret_key), \
             patch("requests.Session.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Network failed")
            res = sync_adzuna_jobs()

        # Ensure the secret key is nowhere in the returned result dictionary
        result_str = str(res)
        self.assertNotIn(secret_key, result_str)

    @patch("requests.Session.get")
    def test_adzuna_multi_query_combination_and_single_reconciliation(self, mock_get):
        # Query 1 (software engineer) returns ID 1001 and 1002
        resp_q1 = MagicMock()
        resp_q1.raise_for_status.return_value = None
        resp_q1.json.return_value = {
            "count": 2,
            "results": [
                {
                    "id": "1001",
                    "title": "Software Engineer",
                    "description": "Python, React remote",
                    "redirect_url": "https://example.com/1001",
                    "company": {"display_name": "Tech Corp"},
                },
                {
                    "id": "1002",
                    "title": "Software Engineer",
                    "description": "Full stack",
                    "redirect_url": "https://example.com/1002",
                    "company": {"display_name": "Tech Corp"},
                },
            ],
        }

        # Query 2 (python developer) returns ID 1002 (overlap with q1) and 1003 (new)
        resp_q2 = MagicMock()
        resp_q2.raise_for_status.return_value = None
        resp_q2.json.return_value = {
            "count": 2,
            "results": [
                {
                    "id": "1002",
                    "title": "Software Engineer - Updated",
                    "description": "Full stack python",
                    "redirect_url": "https://example.com/1002",
                    "company": {"display_name": "Tech Corp"},
                },
                {
                    "id": "1003",
                    "title": "Python Developer",
                    "description": "Django telecommuter",
                    "redirect_url": "https://example.com/1003",
                    "company": {"display_name": "Data Systems"},
                },
            ],
        }

        mock_get.side_effect = [resp_q1, resp_q2]

        source = ExternalJobSource.objects.create(
            name="Adzuna",
            provider_code="adzuna",
            api_enabled=True,
        )
        old_stale_job = ExternalJob.objects.create(
            source=source,
            external_job_id="9999",
            title="Old Stale Job",
            company_name="Old Co",
            description="Desc",
            original_job_url="https://example.com/9999",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(
                what="software engineer|python developer",
                max_pages=1,
            )

        self.assertTrue(res["success"])
        self.assertEqual(res["queries_processed"], 2)
        self.assertEqual(res["pages_fetched"], 2)
        self.assertEqual(res["jobs_received"], 4)
        # 1001 (created), 1002 (created then updated), 1003 (created) -> total created: 3
        self.assertEqual(res["jobs_created"], 3)
        self.assertEqual(res["jobs_updated"], 1)
        self.assertEqual(res["jobs_marked_inactive"], 1)

        # Verify exact unique jobs count in DB
        adzuna_jobs = ExternalJob.objects.filter(source=source, is_active=True)
        self.assertEqual(adzuna_jobs.count(), 3)
        self.assertTrue(adzuna_jobs.filter(external_job_id="1001").exists())
        self.assertTrue(adzuna_jobs.filter(external_job_id="1002").exists())
        self.assertTrue(adzuna_jobs.filter(external_job_id="1003").exists())

        # Verify job 1001 from query 1 was NOT deactivated during query 2
        j1 = ExternalJob.objects.get(source=source, external_job_id="1001")
        self.assertTrue(j1.is_active)

        # Verify old unreferenced job was deactivated during single final reconciliation
        old_stale_job.refresh_from_db()
        self.assertFalse(old_stale_job.is_active)
        self.assertEqual(old_stale_job.status, ExternalJob.Status.INACTIVE)

    @patch("requests.Session.get")
    def test_adzuna_multi_query_distinct_jobs_same_company_title_location(self, mock_get):
        # Two different Adzuna IDs with same company, title, and location must remain distinct records
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "count": 2,
            "results": [
                {
                    "id": "55551",
                    "title": "Software Development Engineer IV",
                    "description": "Desc 1",
                    "redirect_url": "https://example.com/55551",
                    "company": {"display_name": "Premera Blue Cross"},
                    "location": {"display_name": "Wisconsin, US"},
                },
                {
                    "id": "55552",
                    "title": "Software Development Engineer IV",
                    "description": "Desc 2",
                    "redirect_url": "https://example.com/55552",
                    "company": {"display_name": "Premera Blue Cross"},
                    "location": {"display_name": "Wisconsin, US"},
                },
            ],
        }
        mock_get.return_value = resp

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(what="software developer", max_pages=1)

        self.assertTrue(res["success"])
        self.assertEqual(res["jobs_created"], 2)
        self.assertEqual(
            ExternalJob.objects.filter(
                company_name="Premera Blue Cross",
                title="Software Development Engineer IV",
            ).count(),
            2,
        )

    @patch("requests.Session.get")
    def test_adzuna_multi_query_partial_failure_preserves_all_jobs(self, mock_get):
        source = ExternalJobSource.objects.create(
            name="Adzuna",
            provider_code="adzuna",
            api_enabled=True,
        )
        existing_job = ExternalJob.objects.create(
            source=source,
            external_job_id="existing-100",
            title="Existing Active Job",
            company_name="Tech Co",
            description="Desc",
            original_job_url="https://example.com/existing-100",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        # Query 1 succeeds
        resp_q1 = MagicMock()
        resp_q1.raise_for_status.return_value = None
        resp_q1.json.return_value = {
            "count": 1,
            "results": [
                {
                    "id": "2001",
                    "title": "Q1 Role",
                    "description": "Desc",
                    "redirect_url": "https://example.com/2001",
                }
            ],
        }

        # Query 2 fails with 500 error
        resp_q2 = MagicMock()
        resp_q2.raise_for_status.side_effect = requests.HTTPError("500 Internal Server Error")

        mock_get.side_effect = [resp_q1, resp_q2]

        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            res = sync_adzuna_jobs(what="query1|query2", max_pages=1)

        self.assertFalse(res["success"])
        # PARTIAL FAILURE SAFETY: existing job and newly created job from Q1 must remain untouched
        existing_job.refresh_from_db()
        self.assertTrue(existing_job.is_active)
        self.assertEqual(existing_job.status, ExternalJob.Status.ACTIVE)

    @patch("requests.Session.get")
    def test_sync_adzuna_management_command_cli_options(self, mock_get):
        from io import StringIO
        from django.core.management import call_command

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "count": 1,
            "results": [
                {
                    "id": "3001",
                    "title": "CLI Test Role",
                    "description": "Desc",
                    "redirect_url": "https://example.com/3001",
                }
            ],
        }
        mock_get.return_value = resp

        out = StringIO()
        with patch("django.conf.settings.ADZUNA_APP_ID", "dummy_app_id"), \
             patch("django.conf.settings.ADZUNA_APP_KEY", "dummy_app_key"):
            call_command(
                "sync_adzuna",
                what="react developer",
                country="us",
                location="Austin",
                max_pages=1,
                results_per_page=10,
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("Adzuna sync completed", output)
        self.assertIn("Queries (1): react developer", output)
        self.assertIn("Created: 1", output)


class CombinedExternalJobsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pp_source = ExternalJobSource.objects.create(
            name="People Prime",
            provider_code="people_prime",
            api_enabled=True,
            attribution_name="People Prime",
            attribution_url="https://people-prime.com",
        )
        self.adzuna_source = ExternalJobSource.objects.create(
            name="Adzuna",
            provider_code="adzuna",
            api_enabled=True,
            attribution_name="Adzuna",
            attribution_url="https://www.adzuna.com",
        )

    def test_people_prime_remote_and_hybrid_included_onsite_and_unknown_excluded(self):
        # Job A: India Remote
        job_a = ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-1",
            title="Senior React Developer",
            company_name="People Prime",
            location="Bengaluru, Karnataka, India",
            country="IN",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://people-prime.com/job-details?id=pp-1",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # Job B: India Hybrid
        job_b = ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-2",
            title="SAP Consultant",
            company_name="People Prime",
            location="Hyderabad, Telangana",
            country="IN",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://people-prime.com/job-details?id=pp-2",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # Job C: US Remote
        job_c = ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-3",
            title="US Fullstack Engineer",
            company_name="People Prime",
            location="Austin, TX",
            country="US",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://people-prime.com/job-details?id=pp-3",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # Job D: US Hybrid
        job_d = ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-4",
            title="US DevOps Specialist",
            company_name="People Prime",
            location="New York, NY",
            country="US",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://people-prime.com/job-details?id=pp-4",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # Job E: India Onsite (must be excluded)
        job_e = ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-5",
            title="Onsite Operations Manager",
            company_name="People Prime",
            location="Mumbai, Maharashtra",
            country="IN",
            remote_type=ExternalJob.RemoteType.ONSITE,
            original_job_url="https://people-prime.com/job-details?id=pp-5",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # Job F: India Unknown (must be excluded)
        job_f = ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-6",
            title="Business Analyst",
            company_name="People Prime",
            location="Pune, Maharashtra",
            country="IN",
            remote_type=ExternalJob.RemoteType.UNKNOWN,
            original_job_url="https://people-prime.com/job-details?id=pp-6",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = self.client.get("/api/v1/external-jobs/?remote_type=REMOTE,HYBRID")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data["count"], 4)

        returned_ids = {j["external_job_id"] for j in data["results"]}
        self.assertEqual(returned_ids, {"pp-1", "pp-2", "pp-3", "pp-4"})
        self.assertNotIn("pp-5", returned_ids)
        self.assertNotIn("pp-6", returned_ids)

        # Verify preserved country for India and US jobs
        results_by_id = {j["external_job_id"]: j for j in data["results"]}
        self.assertEqual(results_by_id["pp-1"]["country"], "IN")
        self.assertEqual(results_by_id["pp-1"]["remote_type"], "REMOTE")
        self.assertEqual(results_by_id["pp-1"]["source_name"], "People Prime")

        self.assertEqual(results_by_id["pp-2"]["country"], "IN")
        self.assertEqual(results_by_id["pp-2"]["remote_type"], "HYBRID")

        self.assertEqual(results_by_id["pp-3"]["country"], "US")
        self.assertEqual(results_by_id["pp-3"]["remote_type"], "REMOTE")

        self.assertEqual(results_by_id["pp-4"]["country"], "US")
        self.assertEqual(results_by_id["pp-4"]["remote_type"], "HYBRID")

    def test_backward_compatibility_country_us_remote_true(self):
        # People Prime India Remote
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-in-remote",
            title="India Remote Dev",
            company_name="People Prime",
            country="IN",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://people-prime.com/job-details?id=1",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # Adzuna US Remote
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adz-us-remote",
            title="US Remote Dev",
            company_name="Adzuna Employer",
            country="US",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://adzuna.com/job/1",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # Adzuna US Hybrid
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adz-us-hybrid",
            title="US Hybrid Dev",
            company_name="Adzuna Employer",
            country="US",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://adzuna.com/job/2",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        # Existing consumers calling country=US&remote=true
        res = self.client.get("/api/v1/external-jobs/?country=US&remote=true")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["external_job_id"], "adz-us-remote")

    def test_combined_people_prime_and_adzuna_coexistence(self):
        # Adzuna US Remote
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adz-1",
            title="Adzuna Python Lead",
            company_name="Fintech US",
            location="San Francisco, CA",
            country="US",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://adzuna.com/job/adz-1",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # Adzuna US Hybrid
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adz-2",
            title="Adzuna Cloud Architect",
            company_name="Cloud Corp",
            location="Austin, TX",
            country="US",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://adzuna.com/job/adz-2",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # People Prime India Hybrid
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-10",
            title="People Prime Data Engineer",
            company_name="People Prime",
            location="Bengaluru, Karnataka",
            country="IN",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://people-prime.com/job-details?id=pp-10",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # People Prime India Remote
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-11",
            title="People Prime Full Stack Engineer",
            company_name="People Prime",
            location="Pan India",
            country="IN",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://people-prime.com/job-details?id=pp-11",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = self.client.get("/api/v1/external-jobs/?remote_type=REMOTE,HYBRID")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data["count"], 4)

        by_id = {j["external_job_id"]: j for j in data["results"]}

        # Check Adzuna job
        self.assertEqual(by_id["adz-1"]["source_name"], "Adzuna")
        self.assertEqual(by_id["adz-1"]["source_attribution"]["attribution_name"], "Adzuna")
        self.assertEqual(by_id["adz-1"]["country"], "US")
        self.assertEqual(by_id["adz-1"]["remote_type"], "REMOTE")
        self.assertEqual(by_id["adz-1"]["original_job_url"], "https://adzuna.com/job/adz-1")

        # Check People Prime job
        self.assertEqual(by_id["pp-10"]["source_name"], "People Prime")
        self.assertEqual(by_id["pp-10"]["source_attribution"]["attribution_name"], "People Prime")
        self.assertEqual(by_id["pp-10"]["country"], "IN")
        self.assertEqual(by_id["pp-10"]["remote_type"], "HYBRID")
        self.assertEqual(by_id["pp-10"]["original_job_url"], "https://people-prime.com/job-details?id=pp-10")

    def test_remote_type_single_filters(self):
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-r1",
            title="Remote Role",
            company_name="People Prime",
            country="IN",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://people-prime.com/job-details?id=r1",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-h1",
            title="Hybrid Role",
            company_name="People Prime",
            country="IN",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://people-prime.com/job-details?id=h1",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res_remote = self.client.get("/api/v1/external-jobs/?remote_type=REMOTE")
        self.assertEqual(res_remote.json()["count"], 1)
        self.assertEqual(res_remote.json()["results"][0]["external_job_id"], "pp-r1")

        res_hybrid = self.client.get("/api/v1/external-jobs/?remote_type=HYBRID")
        self.assertEqual(res_hybrid.json()["count"], 1)
        self.assertEqual(res_hybrid.json()["results"][0]["external_job_id"], "pp-h1")

    def test_non_us_remote_hybrid_filtering_and_country_preservation(self):
        # 1. India Remote (People Prime) -> Include
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-in-rem",
            title="India Remote Engineer",
            company_name="People Prime",
            location="Bengaluru, Karnataka, India",
            country="IN",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://people-prime.com/job-details?id=1",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 2. India Hybrid (People Prime) -> Include
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-in-hyb",
            title="India Hybrid Lead",
            company_name="People Prime",
            location="Hyderabad, Telangana",
            country="IN",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://people-prime.com/job-details?id=2",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 3. Canada Remote (Adzuna) -> Include
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adz-ca-rem",
            title="Canada Remote Architect",
            company_name="Toronto Tech",
            location="Toronto, ON",
            country="CA",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://adzuna.com/job/ca-1",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 4. UK Hybrid (Adzuna) -> Include
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adz-uk-hyb",
            title="UK Hybrid Consultant",
            company_name="London Systems",
            location="London, UK",
            country="GB",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://adzuna.com/job/uk-1",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 5. US Remote (Adzuna) -> EXCLUDE from non-US section
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adz-us-rem",
            title="US Remote Developer",
            company_name="Austin Cloud",
            location="Austin, TX",
            country="US",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://adzuna.com/job/us-1",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 6. US Hybrid (Adzuna) -> EXCLUDE from non-US section
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adz-us-hyb",
            title="US Hybrid Engineer",
            company_name="NY Systems",
            location="New York, NY",
            country="US",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://adzuna.com/job/us-2",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 7. India Onsite (People Prime) -> EXCLUDE
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-in-onsite",
            title="India Onsite Admin",
            company_name="People Prime",
            location="Mumbai, Maharashtra",
            country="IN",
            remote_type=ExternalJob.RemoteType.ONSITE,
            original_job_url="https://people-prime.com/job-details?id=3",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 8. India Unknown (People Prime) -> EXCLUDE
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="pp-in-unknown",
            title="India Unknown Role",
            company_name="People Prime",
            location="Pune, Maharashtra",
            country="IN",
            remote_type=ExternalJob.RemoteType.UNKNOWN,
            original_job_url="https://people-prime.com/job-details?id=4",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        # Query Non-US Remote/Hybrid endpoint
        res = self.client.get("/api/v1/external-jobs/?exclude_country=US&remote_type=REMOTE,HYBRID")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data["count"], 4)

        returned_ids = {j["external_job_id"] for j in data["results"]}
        self.assertEqual(returned_ids, {"pp-in-rem", "pp-in-hyb", "adz-ca-rem", "adz-uk-hyb"})
        self.assertNotIn("adz-us-rem", returned_ids)
        self.assertNotIn("adz-us-hyb", returned_ids)
        self.assertNotIn("pp-in-onsite", returned_ids)
        self.assertNotIn("pp-in-unknown", returned_ids)

        by_id = {j["external_job_id"]: j for j in data["results"]}
        # Country preservation checks
        self.assertEqual(by_id["pp-in-rem"]["country"], "IN")
        self.assertEqual(by_id["pp-in-rem"]["source_name"], "People Prime")
        self.assertEqual(by_id["pp-in-hyb"]["country"], "IN")
        self.assertEqual(by_id["adz-ca-rem"]["country"], "CA")
        self.assertEqual(by_id["adz-ca-rem"]["source_name"], "Adzuna")
        self.assertEqual(by_id["adz-uk-hyb"]["country"], "GB")

        # Query US Remote/Hybrid endpoint (US Remote Jobs section)
        us_res = self.client.get("/api/v1/external-jobs/?country=US&remote_type=REMOTE,HYBRID")
        self.assertEqual(us_res.status_code, status.HTTP_200_OK)
        us_data = us_res.json()
        self.assertEqual(us_data["count"], 2)
        us_ids = {j["external_job_id"] for j in us_data["results"]}
        self.assertEqual(us_ids, {"adz-us-rem", "adz-us-hyb"})
        # No overlap between sections
        self.assertEqual(returned_ids.intersection(us_ids), set())

    def test_department_classification_rules(self):
        from external_jobs.utils import classify_job_department

        self.assertEqual(classify_job_department(title="Software Engineer"), "Software Engineering")
        self.assertEqual(classify_job_department(title="Backend Developer"), "Software Engineering")
        self.assertEqual(classify_job_department(title="Frontend Developer"), "Software Engineering")
        self.assertEqual(classify_job_department(title="Full Stack Developer"), "Software Engineering")
        self.assertEqual(classify_job_department(title="Data Scientist"), "Data & AI")
        self.assertEqual(classify_job_department(title="Data Engineer"), "Data & AI")
        self.assertEqual(classify_job_department(title="DevOps Engineer"), "DevOps & Cloud")
        self.assertEqual(classify_job_department(title="QA Engineer"), "QA & Testing")
        self.assertEqual(classify_job_department(title="Security Engineer"), "Cybersecurity")
        self.assertEqual(classify_job_department(title="Product Manager"), "Product")
        self.assertEqual(classify_job_department(title="UX Designer"), "Design")
        self.assertEqual(classify_job_department(title="Scrum Master"), "Project Management")
        self.assertEqual(classify_job_department(title="Business Analyst"), "Business & Operations")

    def test_department_api_filtering_and_restoration(self):
        # 1. Software Engineering job
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="dept-swe-1",
            title="Senior Python Backend Engineer",
            company_name="People Prime",
            location="Bengaluru, India",
            country="IN",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://people-prime.com/job-details?id=swe-1",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 2. Data & AI job
        ExternalJob.objects.create(
            source=self.pp_source,
            external_job_id="dept-data-1",
            title="Lead Data Engineer (GCP/Spark)",
            company_name="People Prime",
            location="Hyderabad, India",
            country="IN",
            remote_type=ExternalJob.RemoteType.HYBRID,
            original_job_url="https://people-prime.com/job-details?id=data-1",
            source_name="People Prime",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 3. DevOps & Cloud job
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="dept-devops-1",
            title="DevOps Cloud Architect",
            company_name="Cloud Corp",
            location="Austin, TX",
            country="US",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://adzuna.com/job/devops-1",
            source_name="Adzuna",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        # 10. Selecting Software Engineering shows only Software Engineering jobs
        res_swe = self.client.get("/api/v1/external-jobs/?department=software-engineering")
        self.assertEqual(res_swe.status_code, status.HTTP_200_OK)
        swe_ids = {j["external_job_id"] for j in res_swe.json()["results"]}
        self.assertIn("dept-swe-1", swe_ids)
        self.assertNotIn("dept-data-1", swe_ids)
        self.assertNotIn("dept-devops-1", swe_ids)

        # 11. Selecting Data & AI shows only Data & AI jobs
        res_data = self.client.get("/api/v1/external-jobs/?department=data-ai")
        self.assertEqual(res_data.status_code, status.HTTP_200_OK)
        data_ids = {j["external_job_id"] for j in res_data.json()["results"]}
        self.assertIn("dept-data-1", data_ids)
        self.assertNotIn("dept-swe-1", data_ids)
        self.assertNotIn("dept-devops-1", data_ids)

        # 12. Selecting DevOps & Cloud changes results correctly
        res_devops = self.client.get("/api/v1/external-jobs/?department=devops-cloud")
        self.assertEqual(res_devops.status_code, status.HTTP_200_OK)
        devops_ids = {j["external_job_id"] for j in res_devops.json()["results"]}
        self.assertIn("dept-devops-1", devops_ids)
        self.assertNotIn("dept-swe-1", devops_ids)
        self.assertNotIn("dept-data-1", devops_ids)

        # 13. All Departments (no department param) restores unfiltered results
        res_all = self.client.get("/api/v1/external-jobs/")
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        all_ids = {j["external_job_id"] for j in res_all.json()["results"]}
        self.assertTrue({"dept-swe-1", "dept-data-1", "dept-devops-1"}.issubset(all_ids))

        # Check department field present in serialized output
        job_swe_data = next(j for j in res_swe.json()["results"] if j["external_job_id"] == "dept-swe-1")
        self.assertEqual(job_swe_data["department"], "Software Engineering")
        self.assertEqual(job_swe_data["source_name"], "People Prime")
        self.assertEqual(job_swe_data["country"], "IN")
        self.assertEqual(job_swe_data["remote_type"], "REMOTE")
        self.assertEqual(job_swe_data["original_job_url"], "https://people-prime.com/job-details?id=swe-1")


class HimalayasSyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("requests.Session.get")
    def test_himalayas_sync_single_page_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "jobs": [
                {
                    "title": "Senior React Developer",
                    "companyName": "Acme Corp",
                    "companySlug": "acme-corp",
                    "companyLogo": "https://cdn-images.himalayas.app/acme.png",
                    "employmentType": "Full Time",
                    "minSalary": 120000,
                    "maxSalary": 160000,
                    "salaryPeriod": "annual",
                    "currency": "USD",
                    "locationRestrictions": ["United States"],
                    "categories": ["React", "Frontend"],
                    "parentCategories": ["Developer"],
                    "description": "<p>Build modern web apps in React.</p>",
                    "excerpt": "Build modern web apps.",
                    "pubDate": 1789635875,
                    "expiryDate": 1794819874,
                    "applicationLink": "https://himalayas.app/companies/acme-corp/jobs/react-dev",
                    "guid": "himalayas-job-101",
                },
                {
                    "title": "Worldwide AI Engineer",
                    "companyName": "Global AI Lab",
                    "companySlug": "global-ai",
                    "employmentType": "Full Time",
                    "locationRestrictions": [],  # Worldwide
                    "categories": ["AI-LLM-Engineering", "Python"],
                    "parentCategories": ["Developer"],
                    "description": "<p>Develop cutting-edge LLMs.</p>",
                    "pubDate": 1789635875,
                    "applicationLink": "https://himalayas.app/companies/global-ai/jobs/ai-eng",
                    "guid": "himalayas-job-102",
                },
            ],
            "nextCursor": None,
            "totalCount": 2,
        }
        mock_get.return_value = mock_response

        from external_jobs.providers.himalayas import sync_himalayas_jobs, HIMALAYAS_PROVIDER_CODE
        result = sync_himalayas_jobs()

        self.assertTrue(result["success"])
        self.assertEqual(result["pages_fetched"], 1)
        self.assertEqual(result["jobs_received"], 2)
        self.assertEqual(result["jobs_created"], 2)
        self.assertEqual(result["jobs_marked_inactive"], 0)

        # Verify US job created
        job_us = ExternalJob.objects.get(external_job_id="himalayas-job-101")
        self.assertEqual(job_us.title, "Senior React Developer")
        self.assertEqual(job_us.company_name, "Acme Corp")
        self.assertEqual(job_us.country, "US")
        self.assertEqual(job_us.remote_type, ExternalJob.RemoteType.REMOTE)
        self.assertEqual(job_us.salary_min, 120000)
        self.assertEqual(job_us.salary_max, 160000)
        self.assertEqual(job_us.salary_currency, "USD")
        self.assertEqual(job_us.original_job_url, "https://himalayas.app/companies/acme-corp/jobs/react-dev")
        self.assertEqual(job_us.source_name, "Himalayas")
        self.assertIn("React", job_us.tech_stack)
        self.assertTrue(job_us.is_active)

        # Verify Worldwide job created
        job_global = ExternalJob.objects.get(external_job_id="himalayas-job-102")
        self.assertEqual(job_global.country, "GLOBAL")
        self.assertEqual(job_global.location, "Worldwide (Remote)")
        self.assertEqual(job_global.remote_type, ExternalJob.RemoteType.REMOTE)

        # Test API endpoints integration
        # 1. US Remote Jobs section (country=US)
        res_us = self.client.get("/api/v1/external-jobs/?country=US&remote_type=REMOTE,HYBRID")
        self.assertEqual(res_us.status_code, status.HTTP_200_OK)
        us_ext_ids = [j["external_job_id"] for j in res_us.json()["results"]]
        self.assertIn("himalayas-job-101", us_ext_ids)
        self.assertNotIn("himalayas-job-102", us_ext_ids)

        # 2. Remote / Hybrid section (exclude_country=US)
        res_global = self.client.get("/api/v1/external-jobs/?exclude_country=US&remote_type=REMOTE,HYBRID")
        self.assertEqual(res_global.status_code, status.HTTP_200_OK)
        global_ext_ids = [j["external_job_id"] for j in res_global.json()["results"]]
        self.assertIn("himalayas-job-102", global_ext_ids)
        self.assertNotIn("himalayas-job-101", global_ext_ids)

        # 3. Department classification check
        res_dept_ai = self.client.get("/api/v1/external-jobs/?department=data-ai")
        self.assertEqual(res_dept_ai.status_code, status.HTTP_200_OK)
        ai_ext_ids = [j["external_job_id"] for j in res_dept_ai.json()["results"]]
        self.assertIn("himalayas-job-102", ai_ext_ids)

        # 4. Source attribution check
        job_data = res_us.json()["results"][0]
        self.assertEqual(job_data["source_name"], "Himalayas")
        self.assertEqual(job_data["source_attribution"]["attribution_name"], "Himalayas")
        self.assertEqual(job_data["source_attribution"]["attribution_url"], "https://himalayas.app")

    @patch("requests.Session.get")
    def test_himalayas_cursor_pagination(self, mock_get):
        page1_res = MagicMock()
        page1_res.raise_for_status.return_value = None
        page1_res.json.return_value = {
            "jobs": [
                {
                    "title": "Page 1 Job",
                    "companyName": "Company A",
                    "guid": "him-p1-1",
                    "applicationLink": "https://himalayas.app/jobs/1",
                    "locationRestrictions": ["Canada"],
                }
            ],
            "nextCursor": "cursor_token_page_2",
        }

        page2_res = MagicMock()
        page2_res.raise_for_status.return_value = None
        page2_res.json.return_value = {
            "jobs": [
                {
                    "title": "Page 2 Job",
                    "companyName": "Company B",
                    "guid": "him-p2-1",
                    "applicationLink": "https://himalayas.app/jobs/2",
                    "locationRestrictions": ["Poland"],
                }
            ],
            "nextCursor": None,
        }

        mock_get.side_effect = [page1_res, page2_res]

        from external_jobs.providers.himalayas import sync_himalayas_jobs
        result = sync_himalayas_jobs()

        self.assertTrue(result["success"])
        self.assertEqual(result["pages_fetched"], 2)
        self.assertEqual(result["jobs_received"], 2)
        self.assertEqual(result["jobs_created"], 2)
        self.assertTrue(ExternalJob.objects.filter(external_job_id="him-p1-1").exists())
        self.assertTrue(ExternalJob.objects.filter(external_job_id="him-p2-1").exists())

    @patch("requests.Session.get")
    def test_himalayas_empty_jobs_response(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "jobs": [],
            "nextCursor": None,
        }
        mock_get.return_value = mock_response

        from external_jobs.providers.himalayas import sync_himalayas_jobs
        result = sync_himalayas_jobs()

        self.assertTrue(result["success"])
        self.assertEqual(result["jobs_received"], 0)
        self.assertEqual(result["pages_fetched"], 1)

    @patch("requests.Session.get")
    def test_himalayas_partial_failure_preserves_existing_jobs(self, mock_get):
        from external_jobs.providers.himalayas import get_or_create_himalayas_source, sync_himalayas_jobs
        source = get_or_create_himalayas_source()

        # Seed an existing active job
        existing_job = ExternalJob.objects.create(
            source=source,
            external_job_id="existing-him-1",
            title="Existing Job",
            company_name="Old Co",
            country="US",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://himalayas.app/old",
            source_name="Himalayas",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        page1_res = MagicMock()
        page1_res.raise_for_status.return_value = None
        page1_res.json.return_value = {
            "jobs": [
                {
                    "title": "Page 1 Fresh Job",
                    "companyName": "Fresh Co",
                    "guid": "fresh-him-1",
                    "applicationLink": "https://himalayas.app/fresh",
                }
            ],
            "nextCursor": "cursor_token_page_2",
        }

        # Page 2 fails with HTTP 500
        page2_res = MagicMock()
        page2_res.raise_for_status.side_effect = requests.HTTPError("500 Server Error")

        mock_get.side_effect = [page1_res, page2_res]

        result = sync_himalayas_jobs()

        self.assertFalse(result["success"])
        self.assertEqual(result["pages_fetched"], 1)
        self.assertEqual(result["jobs_marked_inactive"], 0)

        # Existing job must still be ACTIVE (not marked inactive because sync was aborted!)
        existing_job.refresh_from_db()
        self.assertTrue(existing_job.is_active)
        self.assertEqual(existing_job.status, ExternalJob.Status.ACTIVE)

    @patch("requests.Session.get")
    def test_himalayas_stale_reconciliation_on_full_success(self, mock_get):
        from external_jobs.providers.himalayas import get_or_create_himalayas_source, sync_himalayas_jobs
        source = get_or_create_himalayas_source()

        # Seed an existing active job that is not in the new response
        stale_job = ExternalJob.objects.create(
            source=source,
            external_job_id="stale-him-job",
            title="Stale Job",
            company_name="Old Co",
            country="US",
            remote_type=ExternalJob.RemoteType.REMOTE,
            original_job_url="https://himalayas.app/old",
            source_name="Himalayas",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "jobs": [
                {
                    "title": "Active Job",
                    "companyName": "New Co",
                    "guid": "active-him-job",
                    "applicationLink": "https://himalayas.app/active",
                }
            ],
            "nextCursor": None,
        }
        mock_get.return_value = mock_response

        result = sync_himalayas_jobs()
        self.assertTrue(result["success"])
        self.assertEqual(result["jobs_marked_inactive"], 1)

        stale_job.refresh_from_db()
        self.assertFalse(stale_job.is_active)
        self.assertEqual(stale_job.status, ExternalJob.Status.INACTIVE)


class ExternalJobDetailAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.source = ExternalJobSource.objects.create(
            name="Himalayas",
            provider_code="himalayas",
            attribution_name="Himalayas",
            attribution_url="https://himalayas.app",
        )
        self.active_job = ExternalJob.objects.create(
            source=self.source,
            external_job_id="job-active-123",
            title="Senior Backend Engineer",
            company_name="Acme Corp",
            company_website="https://acme.com",
            description="Complete full description for the job posting.",
            location="San Francisco, CA",
            country="US",
            state="CA",
            city="San Francisco",
            remote_type=ExternalJob.RemoteType.REMOTE,
            employment_type="Full-time",
            salary_min=120000,
            salary_max=160000,
            salary_currency="USD",
            tech_stack=["Python", "Django", "PostgreSQL"],
            original_job_url="https://himalayas.app/jobs/acme/senior-backend-engineer",
            source_job_url="https://himalayas.app/jobs/acme/senior-backend-engineer",
            source_name="Himalayas",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
            dedup_hash="abc123deduphash",
            raw_metadata={
                "company_logo": "https://assets.himalayas.app/acme_logo.png",
                "secret_provider_key": "PRIVATE_SECRET_DO_NOT_EXPOSE",
                "internal_sync_id": 9999,
            },
        )
        self.inactive_job = ExternalJob.objects.create(
            source=self.source,
            external_job_id="job-inactive-456",
            title="Inactive Job",
            company_name="Old Co",
            description="Inactive description",
            original_job_url="https://himalayas.app/jobs/old",
            source_name="Himalayas",
            is_active=False,
            status=ExternalJob.Status.INACTIVE,
        )

    def test_active_job_detail_returns_200_and_public_fields(self):
        url = f"/api/v1/external-jobs/{self.active_job.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["id"], str(self.active_job.id))
        self.assertEqual(data["title"], "Senior Backend Engineer")
        self.assertEqual(data["company_name"], "Acme Corp")
        self.assertEqual(data["company_website"], "https://acme.com")
        self.assertEqual(data["description"], "Complete full description for the job posting.")
        self.assertEqual(data["location"], "San Francisco, CA")
        self.assertEqual(data["country"], "US")
        self.assertEqual(data["remote_type"], "REMOTE")
        self.assertEqual(data["employment_type"], "Full-time")
        self.assertEqual(data["department"], "Software Engineering")
        self.assertEqual(float(data["salary_min"]), 120000.0)
        self.assertEqual(float(data["salary_max"]), 160000.0)
        self.assertEqual(data["salary_currency"], "USD")
        self.assertEqual(data["tech_stack"], ["Python", "Django", "PostgreSQL"])
        self.assertEqual(data["original_job_url"], "https://himalayas.app/jobs/acme/senior-backend-engineer")
        self.assertEqual(data["source_name"], "Himalayas")
        self.assertIsNotNone(data["source_attribution"])
        self.assertEqual(data["source_attribution"]["attribution_name"], "Himalayas")
        self.assertEqual(data["source_attribution"]["attribution_url"], "https://himalayas.app")

    def test_company_logo_extraction(self):
        url = f"/api/v1/external-jobs/{self.active_job.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["company_logo"], "https://assets.himalayas.app/acme_logo.png")

    def test_company_logo_invalid_or_missing_returns_null(self):
        no_logo_job = ExternalJob.objects.create(
            source=self.source,
            external_job_id="job-nologo",
            title="Frontend Dev",
            company_name="NoLogo Co",
            description="Desc",
            original_job_url="https://himalayas.app/jobs/nologo",
            source_name="Himalayas",
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
            raw_metadata={"company_logo": "not-a-valid-url"},
        )
        url = f"/api/v1/external-jobs/{no_logo_job.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["company_logo"])

    def test_raw_metadata_and_internal_fields_not_exposed(self):
        url = f"/api/v1/external-jobs/{self.active_job.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Critical security assertions
        self.assertNotIn("raw_metadata", data)
        self.assertNotIn("dedup_hash", data)
        self.assertNotIn("secret_provider_key", data)
        self.assertNotIn("internal_sync_id", data)

    def test_inactive_job_returns_404(self):
        url = f"/api/v1/external-jobs/{self.inactive_job.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_uuid_returns_404(self):
        import uuid
        random_uuid = uuid.uuid4()
        url = f"/api/v1/external-jobs/{random_uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_endpoint_still_functional(self):
        url = "/api/v1/external-jobs/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        # Verify inactive job is not in list results
        result_ids = [r["id"] for r in data["results"]]
        self.assertIn(str(self.active_job.id), result_ids)
        self.assertNotIn(str(self.inactive_job.id), result_ids)


class HimalayasDescriptionNormalizationTests(TestCase):
    def test_01_plain_text_remains_plain_text(self):
        input_text = "Python developer with Django experience."
        self.assertEqual(html_to_plain_text(input_text), "Python developer with Django experience.")

    def test_02_paragraph_html_converted(self):
        raw_html = "<p>Paragraph one.</p><p>Paragraph two.</p>"
        result = html_to_plain_text(raw_html)
        self.assertEqual(result, "Paragraph one.\n\nParagraph two.")

    def test_03_headings_converted(self):
        raw_html = "<h3>Requirements</h3>"
        self.assertEqual(html_to_plain_text(raw_html), "Requirements")

    def test_04_unordered_lists_converted(self):
        raw_html = "<ul><li>Python</li><li>Django</li></ul>"
        result = html_to_plain_text(raw_html)
        self.assertIn("• Python", result)
        self.assertIn("• Django", result)
        self.assertNotIn("<ul>", result)
        self.assertNotIn("<li>", result)

    def test_05_ordered_lists_converted(self):
        raw_html = "<ol><li>First step</li><li>Second step</li></ol>"
        result = html_to_plain_text(raw_html)
        self.assertIn("1. First step", result)
        self.assertIn("2. Second step", result)
        self.assertNotIn("<ol>", result)
        self.assertNotIn("<li>", result)

    def test_06_inline_formatting_tags_removed_text_retained(self):
        raw_html = "<strong>Strong</strong> and <b>Bold</b> and <em>Emphasized</em> and <i>Italic</i>."
        result = html_to_plain_text(raw_html)
        self.assertEqual(result, "Strong and Bold and Emphasized and Italic.")
        self.assertNotIn("<strong>", result)
        self.assertNotIn("<b>", result)
        self.assertNotIn("<em>", result)
        self.assertNotIn("<i>", result)

    def test_07_br_tag_becomes_line_break(self):
        raw_html = "Line one<br>Line two<br/>Line three<br />Line four"
        result = html_to_plain_text(raw_html)
        self.assertEqual(result, "Line one\nLine two\nLine three\nLine four")
        self.assertNotIn("<br", result)

    def test_08_html_entities_decoded(self):
        raw_html = "Join &amp; grow &quot;today&quot; &apos;fast&apos; &nbsp; &mdash; 100&percnt; remote!"
        result = html_to_plain_text(raw_html)
        self.assertEqual(result, 'Join & grow "today" \'fast\' — 100% remote!')

    def test_09_links_preserve_visible_text(self):
        raw_html = '<a href="https://himalayas.app/companies/guidehealth">Guidehealth</a>'
        result = html_to_plain_text(raw_html)
        self.assertEqual(result, "Guidehealth")
        self.assertNotIn("<a", result)
        self.assertNotIn("href", result)

    def test_10_empty_description_remains_empty(self):
        self.assertEqual(html_to_plain_text(""), "")
        self.assertEqual(html_to_plain_text(None), "")
        self.assertEqual(html_to_plain_text("   "), "")

    def test_11_description_containing_no_html_not_damaged(self):
        clean_text = "We are seeking a senior engineer to lead our distributed team.\n\nKey skills: Python, Django, PostgreSQL."
        self.assertEqual(html_to_plain_text(clean_text), clean_text)

    def test_12_realistic_himalayas_description_converted(self):
        raw_html = """
        <p>Introduction text here.</p>
        <h3>What you'll be doing</h3>
        <ul>
            <li><strong>Requirement one</strong>: Build scalable APIs with <a href="https://python.org">Python</a>.</li>
            <li>Requirement two<br>Additional sub-detail.</li>
            <li>Requirement three</li>
        </ul>
        """
        result = html_to_plain_text(raw_html)
        self.assertIn("Introduction text here.", result)
        self.assertIn("What you'll be doing", result)
        self.assertIn("• Requirement one: Build scalable APIs with Python.", result)
        self.assertIn("• Requirement two\nAdditional sub-detail.", result)
        self.assertIn("• Requirement three", result)

    def test_13_final_normalized_description_contains_no_html_tags(self):
        raw_html = """
        <div>
            <h1>Main Title</h1>
            <h2>Sub Heading</h2>
            <h3>Section</h3>
            <p>A paragraph with <strong>bold</strong>, <em>italic</em>, and <a href="https://example.com">a link</a>.<br/></p>
            <ul>
                <li>Bullet item</li>
            </ul>
            <ol>
                <li>Numbered item</li>
            </ol>
        </div>
        """
        result = html_to_plain_text(raw_html)
        forbidden_tag_prefixes = [
            "<p", "</p", "<div", "</div", "<h1", "<h2", "<h3", "<h4", "<h5", "<h6",
            "<ul", "</ul", "<ol", "</ol", "<li", "</li", "<a", "</a", "<strong", "</strong",
            "<em", "</em", "<b", "</b", "<i", "</i", "<br", "<hr", "<span", "</span"
        ]
        for tag in forbidden_tag_prefixes:
            self.assertNotIn(tag, result.lower())

    @patch("requests.Session.get")
    def test_himalayas_sync_stores_normalized_plain_text_description(self, mock_get):
        from external_jobs.providers.himalayas import sync_himalayas_jobs, get_or_create_himalayas_source

        source = get_or_create_himalayas_source()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "jobs": [
                {
                    "title": "Fullstack Developer",
                    "companyName": "TechCo",
                    "guid": "himalayas-clean-desc-job",
                    "applicationLink": "https://himalayas.app/jobs/techco/fullstack",
                    "description": "<div><p>We are looking for a developer.</p><ul><li>React</li><li>Django</li></ul></div>",
                }
            ],
            "nextCursor": None,
        }
        mock_get.return_value = mock_response

        result = sync_himalayas_jobs()
        self.assertTrue(result["success"])

        job = ExternalJob.objects.get(external_job_id="himalayas-clean-desc-job", source=source)
        self.assertNotIn("<div>", job.description)
        self.assertNotIn("<p>", job.description)
        self.assertNotIn("<ul>", job.description)
        self.assertNotIn("<li>", job.description)
        self.assertIn("We are looking for a developer.", job.description)
        self.assertIn("• React", job.description)
        self.assertIn("• Django", job.description)



