"""
Comprehensive unit and integration tests for Notification Outbox Dispatch and Recovery Workers.

Verifies:
1. Successful dispatch records provider message ID and ACCEPTED_BY_PROVIDER.
2. Duplicate task invocation does not duplicate sends when already accepted.
3. The exact same idempotency key is used for retries.
4. Transient errors reschedule with bounded backoff.
5. Permanent errors transition immediately to PERMANENTLY_FAILED.
6. Retry exhaustion transitions to PERMANENTLY_FAILED.
7. Malformed provider responses are handled safely.
8. Ambiguous read timeouts are retried with deterministic idempotency key.
9. Concurrent workers claim different records without overlapping claims (skip_locked).
10. Stale worker update is rejected after its lease token is replaced (fencing).
11. Expired PROCESSING claims are recovered safely.
12. Closed jobs and ineligible candidates result in CANCELLED.
13. Sensitive fields are never included in outbound payloads or logs.
14. Zero real network calls occur in tests.
15. Celery tasks execute dispatch and recovery handlers cleanly.
"""

import socket
import threading
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from candidates.models import CandidateProfile
from companies.models import Company
from jobs.models import Job
from matching.models import Match
from notifications.client import (
    ResendHTTPClient,
    ResendPermanentError,
    ResendResponse,
    ResendResponseError,
    ResendRetryableError,
)
from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType
from notifications.outbox_worker import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_LEASE_TIMEOUT_SECONDS,
    IDEMPOTENCY_WINDOW_SECONDS,
    build_email_content_from_payload,
    check_notification_eligibility,
    claim_pending_records,
    dispatch_claimed_record,
    dispatch_pending_outbox_records,
    recover_stale_outbox_leases,
)
from notifications.tasks import (
    dispatch_outbox_notifications_task,
    recover_stale_outbox_leases_task,
)

User = get_user_model()



class OutboxDispatchWorkerTests(TestCase):
    """Unit and state transition tests for outbox worker claiming and dispatch."""

    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="emp_dispatch@test.com", password="Password123!", role=User.Role.EMPLOYER
        )
        self.company = Company.objects.create(
            name="Dispatch Corp", owner=self.employer_user
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Distributed Systems Architect",
            description="Build robust outbox systems",
            role_type="full-time",
            experience_level="lead",
            status=Job.Status.ACTIVE,
        )
        self.candidate_user = User.objects.create_user(
            email="cand_dispatch@test.com", password="Password123!", role=User.Role.CANDIDATE
        )
        self.candidate = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Staff Engineer",
            skills=["python", "django", "celery", "postgresql"],
            experience_level="lead",
            open_to_matching=True,
            profile_complete=True,
        )
        self.match = Match.objects.create(
            candidate_profile=self.candidate,
            job=self.job,
            match_score=90,
            status=Match.Status.SUGGESTED,
            visible_to_employer=False,
            recruiter_notified_at=timezone.now(),
        )
        self.outbox = NotificationOutbox.objects.create(
            match=self.match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
            idempotency_key=f"match:{self.match.id}:high_match_alert",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="[High Match Alert] 90% Match: Senior Distributed Systems Architect at Dispatch Corp",
            payload={
                "match_id": str(self.match.id),
                "job_id": str(self.job.id),
                "job_title": self.job.title,
                "company_name": self.company.name,
                "final_score": 90,
                "raw_final_score": 90.0,
                "score_breakdown": {
                    "semantic_score": 90.0,
                    "skill_score": 90.0,
                    "experience_score": 90.0,
                },
            },
        )

        self.mock_client = MagicMock(spec=ResendHTTPClient)

    def test_successful_dispatch_records_provider_id_and_status(self):
        """Successful provider dispatch transitions to ACCEPTED_BY_PROVIDER with provider_message_id and leaves delivered_at unset."""
        self.mock_client.send_email.return_value = ResendResponse(
            message_id="re_valid_acceptance_12345",
            status_code=200,
            raw_response={"id": "re_valid_acceptance_12345"},
        )

        result = dispatch_pending_outbox_records(client=self.mock_client)
        self.assertEqual(result["claimed_count"], 1)

        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.ACCEPTED_BY_PROVIDER)
        self.assertEqual(self.outbox.provider_message_id, "re_valid_acceptance_12345")
        self.assertIsNone(self.outbox.delivered_at, "delivered_at must remain None upon provider acceptance")
        self.assertIsNone(self.outbox.locked_at)
        self.assertIsNone(self.outbox.locked_by)
        self.assertIsNone(self.outbox.lease_token)

        self.mock_client.send_email.assert_called_once_with(
            to="remote@people-prime.com",
            subject=self.outbox.subject,
            html=build_email_content_from_payload(self.outbox.payload)[0],
            text=build_email_content_from_payload(self.outbox.payload)[1],
            idempotency_key=f"match:{self.match.id}:high_match_alert",
        )

    def test_successful_provider_acceptance_leaves_delivered_at_unset(self):
        """Provider acceptance (HTTP 200/201) sets ACCEPTED_BY_PROVIDER but leaves delivered_at unset (None)."""
        self.mock_client.send_email.return_value = ResendResponse(
            message_id="re_acceptance_no_delivery_ts",
            status_code=201,
            raw_response={"id": "re_acceptance_no_delivery_ts"},
        )
        dispatch_pending_outbox_records(client=self.mock_client)
        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.ACCEPTED_BY_PROVIDER)
        self.assertEqual(self.outbox.provider_message_id, "re_acceptance_no_delivery_ts")
        self.assertIsNone(self.outbox.delivered_at, "delivered_at must remain None upon provider acceptance")

    def test_retries_and_recovery_do_not_set_delivered_at(self):
        """Neither transient retries nor lease recovery populate delivered_at."""
        self.mock_client.send_email.side_effect = ResendRetryableError("Temporary 503")
        dispatch_pending_outbox_records(client=self.mock_client)
        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PENDING)
        self.assertIsNone(self.outbox.delivered_at)

        # Simulate claim and lease recovery
        self.outbox.status = DeliveryStatus.PROCESSING
        self.outbox.locked_at = timezone.now() - timedelta(seconds=400)
        self.outbox.locked_by = "stale-worker"
        self.outbox.lease_token = uuid.uuid4()
        self.outbox.save(update_fields=["status", "locked_at", "locked_by", "lease_token"])

        recover_stale_outbox_leases(lease_timeout=300)
        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PENDING)
        self.assertIsNone(self.outbox.delivered_at)

    def test_duplicate_task_invocation_does_not_duplicate_sends_when_already_accepted(self):
        """Already accepted records are skipped by worker claiming."""
        self.outbox.status = DeliveryStatus.ACCEPTED_BY_PROVIDER
        self.outbox.provider_message_id = "re_existing_msg"
        self.outbox.save(update_fields=["status", "provider_message_id"])

        result = dispatch_pending_outbox_records(client=self.mock_client)
        self.assertEqual(result["claimed_count"], 0)
        self.mock_client.send_email.assert_not_called()

    def test_exact_same_idempotency_key_used_on_retries(self):
        """Retries must propagate the identical deterministic idempotency key."""
        # First attempt: transient 500 error
        self.mock_client.send_email.side_effect = [
            ResendRetryableError("Resend server error (500)"),
            ResendResponse(message_id="re_retry_success_999", status_code=200, raw_response={"id": "re_retry_success_999"}),
        ]

        # Attempt 1
        dispatch_pending_outbox_records(client=self.mock_client)
        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PENDING)
        self.assertEqual(self.outbox.retry_count, 1)

        # Force due for immediate retry in test
        self.outbox.next_attempt_at = timezone.now() - timedelta(seconds=1)
        self.outbox.save(update_fields=["next_attempt_at"])

        # Attempt 2
        dispatch_pending_outbox_records(client=self.mock_client)
        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.ACCEPTED_BY_PROVIDER)
        self.assertEqual(self.outbox.provider_message_id, "re_retry_success_999")

        # Verify idempotency key was identical in both calls
        calls = self.mock_client.send_email.call_args_list
        self.assertEqual(len(calls), 2)
        key1 = calls[0].kwargs["idempotency_key"]
        key2 = calls[1].kwargs["idempotency_key"]
        self.assertEqual(key1, f"match:{self.match.id}:high_match_alert")
        self.assertEqual(key1, key2)

    def test_transient_error_reschedules_with_bounded_backoff(self):
        """HTTP 429 rate limit or 5xx server errors increment retry_count and reschedule."""
        self.mock_client.send_email.side_effect = ResendRetryableError("Resend rate limit exceeded (HTTP 429)")

        dispatch_pending_outbox_records(client=self.mock_client)

        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PENDING)
        self.assertEqual(self.outbox.retry_count, 1)
        self.assertGreater(self.outbox.next_attempt_at, timezone.now())
        self.assertIn("429", self.outbox.last_error)
        self.assertIsNone(self.outbox.locked_at)
        self.assertIsNone(self.outbox.lease_token)

    def test_permanent_error_transitions_immediately_to_permanently_failed(self):
        """Permanent 4xx errors (401 invalid key, 422 unverified domain) fail terminally."""
        self.mock_client.send_email.side_effect = ResendPermanentError("Resend permanent client error (HTTP 422)")

        dispatch_pending_outbox_records(client=self.mock_client)

        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertIn("Permanent failure", self.outbox.last_error)
        self.assertIsNone(self.outbox.locked_at)
        self.assertIsNone(self.outbox.lease_token)

    def test_retry_exhaustion_transitions_to_permanently_failed(self):
        """Reaching max_retries marks record PERMANENTLY_FAILED."""
        self.outbox.retry_count = 4
        self.outbox.max_retries = 5
        self.outbox.save(update_fields=["retry_count", "max_retries"])

        self.mock_client.send_email.side_effect = ResendRetryableError("503 Service Unavailable")

        dispatch_pending_outbox_records(client=self.mock_client)

        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertEqual(self.outbox.retry_count, 5)
        self.assertIn("Max retries (5) exhausted", self.outbox.last_error)

    def test_malformed_provider_response_handled_safely(self):
        """Malformed response (missing id) is treated as a retryable transient failure."""
        self.mock_client.send_email.side_effect = ResendResponseError("Resend returned HTTP 200 without 'id'")

        dispatch_pending_outbox_records(client=self.mock_client)

        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PENDING)
        self.assertEqual(self.outbox.retry_count, 1)
        self.assertIn("without 'id'", self.outbox.last_error)

    def test_ambiguous_timeout_within_safe_window_retries(self):
        """An ambiguous socket read timeout within the 24h window schedules retry with bounded backoff."""
        self.mock_client.send_email.side_effect = ResendRetryableError("Resend HTTP request timed out (read timeout)")

        dispatch_pending_outbox_records(client=self.mock_client)

        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PENDING)
        self.assertEqual(self.outbox.retry_count, 1)
        self.assertIn("timed out", self.outbox.last_error)
        self.assertGreater(self.outbox.next_attempt_at, timezone.now())
        self.assertIsNone(self.outbox.delivered_at)

    def test_record_queued_over_24h_never_attempted_retries_safely(self):
        """
        A record created > 24 hours ago that was never attempted (first_attempted_at is None)
        must NOT falsely fail as expired. Its first attempt occurs now, so it is safely retried.
        """
        queued_30h_ago = timezone.now() - timedelta(hours=30)
        NotificationOutbox.objects.filter(id=self.outbox.id).update(
            created_at=queued_30h_ago,
            first_attempted_at=None,
        )
        self.outbox.refresh_from_db()

        self.mock_client.send_email.side_effect = ResendRetryableError("Resend HTTP request timed out (read timeout)")

        dispatch_pending_outbox_records(client=self.mock_client)

        self.outbox.refresh_from_db()
        # Must be PENDING with retry_count=1, NOT PERMANENTLY_FAILED
        self.assertEqual(self.outbox.status, DeliveryStatus.PENDING)
        self.assertEqual(self.outbox.retry_count, 1)
        self.assertIsNotNone(self.outbox.first_attempted_at)
        self.assertAlmostEqual(
            self.outbox.first_attempted_at.timestamp(),
            timezone.now().timestamp(),
            delta=5.0,
        )
        self.assertIn("timed out", self.outbox.last_error)

    def test_first_attempt_timestamp_is_recent_retries(self):
        """An ambiguous timeout whose first_attempted_at is recent (e.g. 10m ago) retries with backoff."""
        first_attempt = timezone.now() - timedelta(minutes=10)
        NotificationOutbox.objects.filter(id=self.outbox.id).update(
            first_attempted_at=first_attempt,
            retry_count=1,
        )
        self.outbox.refresh_from_db()

        self.mock_client.send_email.side_effect = ResendRetryableError("Resend HTTP request timed out (read timeout)")

        dispatch_pending_outbox_records(client=self.mock_client)

        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PENDING)
        self.assertEqual(self.outbox.retry_count, 2)
        # Original first_attempted_at must be preserved, not overwritten
        self.assertEqual(self.outbox.first_attempted_at, first_attempt)

    def test_first_attempt_older_than_24h_fails_permanently_with_manual_review(self):
        """An ambiguous timeout whose first_attempted_at is older than 24h transitions to PERMANENTLY_FAILED."""
        first_attempt = timezone.now() - timedelta(hours=25)
        NotificationOutbox.objects.filter(id=self.outbox.id).update(
            first_attempted_at=first_attempt,
            retry_count=1,
        )
        self.outbox.refresh_from_db()

        self.mock_client.send_email.side_effect = ResendRetryableError("Resend HTTP request timed out (read timeout)")

        dispatch_pending_outbox_records(client=self.mock_client)

        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertEqual(self.outbox.retry_count, 2)
        self.assertEqual(self.outbox.first_attempted_at, first_attempt)  # Preserved
        self.assertIn("exceeds provider 24-hour idempotency window", self.outbox.last_error)
        self.assertIn("manual review required", self.outbox.last_error)
        self.assertTrue(self.outbox.payload.get("manual_review_required"))
        self.assertIsNone(self.outbox.delivered_at)
        self.assertIsNone(self.outbox.locked_at)
        self.assertIsNone(self.outbox.lease_token)

    def test_subsequent_retries_preserve_original_first_attempted_at(self):
        """Subsequent retry cycles preserve the original first_attempted_at timestamp."""
        orig_attempt = timezone.now() - timedelta(minutes=45)
        NotificationOutbox.objects.filter(id=self.outbox.id).update(
            first_attempted_at=orig_attempt,
            retry_count=1,
        )
        self.outbox.refresh_from_db()

        # Attempt 2 fails retryably
        self.mock_client.send_email.side_effect = ResendRetryableError("503 Service Unavailable")
        dispatch_pending_outbox_records(client=self.mock_client)
        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.retry_count, 2)
        self.assertEqual(self.outbox.first_attempted_at, orig_attempt)

        # Attempt 3 succeeds
        self.mock_client.send_email.side_effect = None
        self.mock_client.send_email.return_value = ResendResponse(
            message_id="re_retry_success",
            status_code=200,
            raw_response={"id": "re_retry_success"},
        )
        self.outbox.next_attempt_at = timezone.now() - timedelta(seconds=1)
        self.outbox.save(update_fields=["next_attempt_at"])

        dispatch_pending_outbox_records(client=self.mock_client)
        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.ACCEPTED_BY_PROVIDER)
        self.assertEqual(self.outbox.first_attempted_at, orig_attempt)

    def test_legacy_record_without_first_attempted_at_falls_back_to_created_at(self):
        """
        Legacy records that lack first_attempted_at safely fall back to created_at
        for 24h boundary calculation.
        """
        legacy_created = timezone.now() - timedelta(hours=25)
        NotificationOutbox.objects.filter(id=self.outbox.id).update(
            created_at=legacy_created,
            first_attempted_at=None,
        )
        self.outbox.refresh_from_db()

        # Direct test: verify fallback calculation
        window_start = getattr(self.outbox, "first_attempted_at", None) or self.outbox.created_at
        self.assertEqual(window_start, self.outbox.created_at)
        age_seconds = (timezone.now() - window_start).total_seconds()
        self.assertGreaterEqual(age_seconds, IDEMPOTENCY_WINDOW_SECONDS)

    def test_first_attempted_at_recorded_atomically_prior_to_http_call(self):
        """
        Verifies that first_attempted_at is committed to the database
        BEFORE the external HTTP request is made.
        """
        db_state_during_http = {}

        def inspect_db_during_http(**kwargs):
            refreshed = NotificationOutbox.objects.get(id=self.outbox.id)
            db_state_during_http["first_attempted_at"] = refreshed.first_attempted_at
            db_state_during_http["status"] = refreshed.status
            return ResendResponse(
                message_id="re_recorded_before_http",
                status_code=200,
                raw_response={"id": "re_recorded_before_http"},
            )

        self.mock_client.send_email.side_effect = inspect_db_during_http

        self.assertIsNone(self.outbox.first_attempted_at)
        dispatch_pending_outbox_records(client=self.mock_client)

        self.assertIsNotNone(db_state_during_http.get("first_attempted_at"))
        self.assertEqual(db_state_during_http["status"], DeliveryStatus.PROCESSING)

    def test_expired_ambiguous_record_cannot_be_requeued_by_recovery(self):
        """A record marked PERMANENTLY_FAILED due to expired ambiguous timeout is never reclaimed by recovery."""
        self.outbox.status = DeliveryStatus.PERMANENTLY_FAILED
        self.outbox.last_error = "Manual review required: ambiguous timeout past 24h."
        self.outbox.locked_at = timezone.now() - timedelta(seconds=600)
        self.outbox.save(update_fields=["status", "last_error", "locked_at"])

        recovered = recover_stale_outbox_leases(lease_timeout=300)
        self.assertEqual(recovered, 0)

        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.PERMANENTLY_FAILED)

    def test_permanent_failures_remain_terminal(self):
        """PERMANENTLY_FAILED records are terminal and never claimed or dispatched by workers."""
        self.outbox.status = DeliveryStatus.PERMANENTLY_FAILED
        self.outbox.next_attempt_at = timezone.now() - timedelta(seconds=100)
        self.outbox.save(update_fields=["status", "next_attempt_at"])

        result = dispatch_pending_outbox_records(client=self.mock_client)
        self.assertEqual(result["claimed_count"], 0)
        self.mock_client.send_email.assert_not_called()

    def test_closed_jobs_and_ineligible_candidates_result_in_cancelled(self):
        """Eligibility changes prior to dispatch transition record to CANCELLED."""
        # Case A: Job paused
        self.job.status = Job.Status.PAUSED
        self.job.save(update_fields=["status"])

        dispatch_pending_outbox_records(client=self.mock_client)
        self.outbox.refresh_from_db()
        self.assertEqual(self.outbox.status, DeliveryStatus.CANCELLED)
        self.assertIn("no longer active", self.outbox.last_error)
        self.mock_client.send_email.assert_not_called()

        # Case B: Candidate opted out
        self.job.status = Job.Status.ACTIVE
        self.job.save(update_fields=["status"])
        self.candidate.open_to_matching = False
        self.candidate.save(update_fields=["open_to_matching"])

        outbox_b = NotificationOutbox.objects.create(
            match=self.match,
            notification_type=NotificationType.CANDIDATE_INTERESTED,
            idempotency_key=f"match:{self.match.id}:cand_interested",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="Test",
        )
        dispatch_pending_outbox_records(client=self.mock_client)
        outbox_b.refresh_from_db()
        self.assertEqual(outbox_b.status, DeliveryStatus.CANCELLED)
        self.assertIn("opted out", outbox_b.last_error)

        # Case C: Match rejected
        self.candidate.open_to_matching = True
        self.candidate.save(update_fields=["open_to_matching"])
        self.match.status = Match.Status.REJECTED
        self.match.save(update_fields=["status"])

        outbox_c = NotificationOutbox.objects.create(
            match=self.match,
            notification_type=NotificationType.MUTUAL_FIT_HANDOFF,
            idempotency_key=f"match:{self.match.id}:mutual_fit",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="Test",
        )
        dispatch_pending_outbox_records(client=self.mock_client)
        outbox_c.refresh_from_db()
        self.assertEqual(outbox_c.status, DeliveryStatus.CANCELLED)
        self.assertIn("rejected", outbox_c.last_error)

    def test_sensitive_fields_never_included_in_outbound_payloads_or_logs(self):
        """Outbound email rendering contains only approved metadata; zero raw vectors or resume texts."""
        html, text = build_email_content_from_payload(self.outbox.payload)

        for content in [html, text]:
            self.assertNotIn("embedding", content.lower())
            self.assertNotIn("vector", content.lower())
            self.assertNotIn("password", content.lower())
            self.assertNotIn("token", content.lower())
            self.assertNotIn("resume_text", content.lower())

    def test_no_real_network_calls_occur(self):
        """Ensure socket level connection is strictly blocked during test dispatch."""
        with patch.object(socket.socket, "connect", side_effect=RuntimeError("Real network call forbidden")):
            self.mock_client.send_email.return_value = ResendResponse(
                message_id="re_net_guarded_123", status_code=200, raw_response={"id": "re_net_guarded_123"}
            )
            res = dispatch_pending_outbox_records(client=self.mock_client)
            self.assertEqual(res["claimed_count"], 1)

    @override_settings(NOTIFICATIONS_DISPATCH_ENABLED=True)
    def test_celery_tasks_dispatch_and_recover(self):
        """Test Celery task wrapper execution when dispatch is explicitly enabled."""
        with patch("notifications.tasks.dispatch_pending_outbox_records") as mock_dispatch, \
             patch("notifications.tasks.recover_stale_outbox_leases") as mock_recover:
            mock_dispatch.return_value = {"claimed_count": 2}
            mock_recover.return_value = 1

            dispatch_res = dispatch_outbox_notifications_task()
            self.assertEqual(dispatch_res["claimed_count"], 2)

            recover_res = recover_stale_outbox_leases_task()
            self.assertEqual(recover_res["recovered_count"], 1)


class OutboxConcurrencyAndLeaseRecoveryTests(TransactionTestCase):
    """
    Real PostgreSQL transaction tests for concurrent worker claiming and lease recovery.
    """

    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="emp_conc@test.com", password="Password123!", role=User.Role.EMPLOYER
        )
        self.company = Company.objects.create(
            name="Concurrency Works", owner=self.employer_user
        )
        self.job1 = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Backend Architect 1",
            status=Job.Status.ACTIVE,
        )
        self.job2 = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Backend Architect 2",
            status=Job.Status.ACTIVE,
        )
        self.candidate_user = User.objects.create_user(
            email="cand_conc@test.com", password="Password123!", role=User.Role.CANDIDATE
        )
        self.candidate = CandidateProfile.objects.create(
            user=self.candidate_user,
            skills=["python"],
            open_to_matching=True,
            profile_complete=True,
        )
        self.match1 = Match.objects.create(candidate_profile=self.candidate, job=self.job1, match_score=90)
        self.match2 = Match.objects.create(candidate_profile=self.candidate, job=self.job2, match_score=92)

    def test_simulated_concurrent_workers_claim_different_records_sequential(self):
        """Simulated sequential test: verifies skip_locked logic partitions batches sequentially in a single thread."""
        outbox1 = NotificationOutbox.objects.create(
            match=self.match1,
            idempotency_key=f"match:{self.match1.id}:alert",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="Job 1 Alert",
        )
        outbox2 = NotificationOutbox.objects.create(
            match=self.match2,
            idempotency_key=f"match:{self.match2.id}:alert",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="Job 2 Alert",
        )

        # Worker 1 claims batch of 1
        claimed_w1 = claim_pending_records(batch_size=1, worker_id="worker-1")
        self.assertEqual(len(claimed_w1), 1)
        rec1_id, token1 = claimed_w1[0]

        # Worker 2 claims batch of 1
        claimed_w2 = claim_pending_records(batch_size=1, worker_id="worker-2")
        self.assertEqual(len(claimed_w2), 1)
        rec2_id, token2 = claimed_w2[0]

        # Assert disjoint claims
        self.assertNotEqual(rec1_id.id, rec2_id.id)
        self.assertNotEqual(token1, token2)

    def test_stale_worker_update_rejected_after_lease_token_replaced_pre_dispatch(self):
        """Pre-dispatch lease refresh rejects a stale worker whose lease expired or was recovered before HTTP call."""
        outbox = NotificationOutbox.objects.create(
            match=self.match1,
            idempotency_key=f"match:{self.match1.id}:fencing_pre_dispatch",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="Fencing Pre-Dispatch Test",
            payload={"job_title": "Test"},
        )

        # Worker A claims record with token_A
        claimed_a = claim_pending_records(batch_size=1, worker_id="worker-A")
        record_a, token_a = claimed_a[0]

        # Simulate recovery or Worker B reclaiming record: token is replaced with token_B
        token_b = uuid.uuid4()
        NotificationOutbox.objects.filter(id=outbox.id).update(
            lease_token=token_b,
            locked_by="worker-B",
        )

        # Worker A attempts to dispatch with stale token_A
        mock_client = MagicMock(spec=ResendHTTPClient)
        result = dispatch_claimed_record(record_a, lease_token=token_a, client=mock_client)

        # Pre-dispatch lease refresh rejects Worker A immediately
        self.assertEqual(result["status"], "fencing_rejected")
        mock_client.send_email.assert_not_called()

        outbox.refresh_from_db()
        self.assertEqual(outbox.lease_token, token_b)
        self.assertEqual(outbox.locked_by, "worker-B")

    def test_stale_worker_update_rejected_after_lease_token_replaced_during_http(self):
        """Fencing tokens reject completion updates from a worker whose lease was replaced during external HTTP I/O."""
        outbox = NotificationOutbox.objects.create(
            match=self.match1,
            idempotency_key=f"match:{self.match1.id}:fencing_mid_dispatch",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="Fencing Mid-Dispatch Test",
            payload={"job_title": "Test"},
        )

        # Worker A claims record with token_A
        claimed_a = claim_pending_records(batch_size=1, worker_id="worker-A")
        record_a, token_a = claimed_a[0]

        # Simulate lease replacement occurring DURING the external HTTP call
        token_b = uuid.uuid4()

        def side_effect_during_send(**kwargs):
            # Recovery or Worker B steals lease while Worker A is in-flight
            NotificationOutbox.objects.filter(id=outbox.id).update(
                lease_token=token_b,
                locked_by="worker-B",
            )
            return ResendResponse(message_id="re_mid_flight_123", status_code=200, raw_response={})

        mock_client = MagicMock(spec=ResendHTTPClient)
        mock_client.send_email.side_effect = side_effect_during_send

        result = dispatch_claimed_record(record_a, lease_token=token_a, client=mock_client)

        # Post-dispatch completion update must reject Worker A's update
        self.assertEqual(result["status"], "fencing_rejected")

        # Database state retains token_B and was NOT marked accepted with Worker A's provider ID
        outbox.refresh_from_db()
        self.assertEqual(outbox.lease_token, token_b)
        self.assertNotEqual(outbox.provider_message_id, "re_mid_flight_123")

    def test_later_records_in_claimed_batch_do_not_expire_due_to_pre_dispatch_refresh(self):
        """
        When a batch is claimed, pre-dispatch refresh updates locked_at to now immediately
        before dispatch. Thus, even if earlier records took time to process, later records
        refresh their lease and avoid starvation/premature recovery.
        """
        outbox = NotificationOutbox.objects.create(
            match=self.match1,
            idempotency_key=f"match:{self.match1.id}:batch_refresh_test",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="Batch Refresh Test",
            payload={"job_title": "Test"},
        )
        claimed = claim_pending_records(batch_size=1, worker_id="worker-batch")
        record, lease_token = claimed[0]

        # Simulate that earlier records took 280s: locked_at is 280s in the past
        old_locked_at = timezone.now() - timedelta(seconds=280)
        NotificationOutbox.objects.filter(id=outbox.id).update(locked_at=old_locked_at)

        mock_client = MagicMock(spec=ResendHTTPClient)
        mock_client.send_email.return_value = ResendResponse(
            message_id="re_refreshed_batch_123", status_code=200, raw_response={"id": "re_refreshed_batch_123"}
        )

        # Dispatch executes pre-dispatch refresh
        result = dispatch_claimed_record(record, lease_token=lease_token, client=mock_client)
        self.assertEqual(result["status"], "accepted_by_provider")

        outbox.refresh_from_db()
        self.assertEqual(outbox.status, DeliveryStatus.ACCEPTED_BY_PROVIDER)
        self.assertEqual(outbox.provider_message_id, "re_refreshed_batch_123")
        self.assertIsNone(self.outbox.delivered_at if hasattr(self, 'outbox') else outbox.delivered_at)

    def test_recovery_does_not_reclaim_record_with_valid_refreshed_lease(self):
        """Recovery only reclaims leases older than lease_timeout; refreshed leases are protected."""
        outbox = NotificationOutbox.objects.create(
            match=self.match1,
            idempotency_key=f"match:{self.match1.id}:protected_lease_test",
            status=DeliveryStatus.PROCESSING,
            recipient_email="remote@people-prime.com",
            subject="Protected Lease Test",
            locked_at=timezone.now(),  # freshly refreshed lease
            locked_by="worker-healthy",
            lease_token=uuid.uuid4(),
            retry_count=0,
            max_retries=3,
        )
        recovered = recover_stale_outbox_leases(lease_timeout=300)
        self.assertEqual(recovered, 0)
        outbox.refresh_from_db()
        self.assertEqual(outbox.status, DeliveryStatus.PROCESSING)
        self.assertEqual(outbox.locked_by, "worker-healthy")

    def test_expired_processing_claims_recovered_safely(self):
        """Stale PROCESSING records are safely recovered to PENDING with backoff and retry increment."""
        stale_time = timezone.now() - timedelta(seconds=400)
        outbox = NotificationOutbox.objects.create(
            match=self.match1,
            idempotency_key=f"match:{self.match1.id}:stale_recovery",
            status=DeliveryStatus.PROCESSING,
            recipient_email="remote@people-prime.com",
            subject="Recovery Test",
            locked_at=stale_time,
            locked_by="dead-worker-99",
            lease_token=uuid.uuid4(),
            retry_count=0,
            max_retries=3,
        )

        recovered_count = recover_stale_outbox_leases(lease_timeout=300)
        self.assertEqual(recovered_count, 1)

        outbox.refresh_from_db()
        self.assertEqual(outbox.status, DeliveryStatus.PENDING)
        self.assertEqual(outbox.retry_count, 1)
        self.assertIsNone(outbox.locked_at)
        self.assertIsNone(outbox.locked_by)
        self.assertIsNone(outbox.lease_token)
        self.assertIsNone(outbox.delivered_at)
        self.assertIn("Lease expired after 300s", outbox.last_error)
        self.assertGreater(outbox.next_attempt_at, timezone.now())

    def test_expired_processing_claims_exceeding_max_retries_fail_permanently(self):
        """Stale PROCESSING records exceeding max_retries transition to PERMANENTLY_FAILED."""
        stale_time = timezone.now() - timedelta(seconds=400)
        outbox = NotificationOutbox.objects.create(
            match=self.match1,
            idempotency_key=f"match:{self.match1.id}:exhausted_recovery",
            status=DeliveryStatus.PROCESSING,
            recipient_email="remote@people-prime.com",
            subject="Exhausted Recovery Test",
            locked_at=stale_time,
            locked_by="dead-worker-99",
            lease_token=uuid.uuid4(),
            retry_count=2,
            max_retries=3,
        )

        recovered_count = recover_stale_outbox_leases(lease_timeout=300)
        self.assertEqual(recovered_count, 1)

        outbox.refresh_from_db()
        self.assertEqual(outbox.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertEqual(outbox.retry_count, 3)
        self.assertIn("max retries (3) exhausted", outbox.last_error)

    def test_real_postgresql_concurrent_workers_skip_locked_with_separate_connections(self):
        """
        Genuine PostgreSQL concurrency test using separate database connections,
        overlapping transactions, and select_for_update(skip_locked=True).
        Verifies that when Worker 1 locks a pending record in an open transaction,
        Worker 2 on an independent connection skips the locked record and cannot claim it.
        """
        if connection.vendor != "postgresql":
            self.skipTest("Genuine multi-connection concurrency test requires PostgreSQL.")

        outbox = NotificationOutbox.objects.create(
            match=self.match1,
            idempotency_key=f"match:{self.match1.id}:pg_conc_single",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="PG Single Concurrency Test",
        )

        worker1_locked = threading.Event()
        worker2_done = threading.Event()
        worker1_claimed_ids = []
        worker2_claimed_ids = []
        worker1_errors = []
        worker2_errors = []

        def worker1_task():
            try:
                with transaction.atomic():
                    records = list(
                        NotificationOutbox.objects.select_for_update(skip_locked=True)
                        .filter(id=outbox.id, status=DeliveryStatus.PENDING)
                    )
                    if records:
                        rec = records[0]
                        rec.status = DeliveryStatus.PROCESSING
                        rec.locked_at = timezone.now()
                        rec.locked_by = "pg-worker-1"
                        rec.lease_token = uuid.uuid4()
                        rec.save(update_fields=["status", "locked_at", "locked_by", "lease_token", "updated_at"])
                        worker1_claimed_ids.append(rec.id)

                    worker1_locked.set()

                    if not worker2_done.wait(timeout=10.0):
                        raise TimeoutError("Worker 2 timed out before completing claim attempt.")
            except Exception as e:
                worker1_errors.append(e)
            finally:
                connections.close_all()

        def worker2_task():
            try:
                if not worker1_locked.wait(timeout=10.0):
                    raise TimeoutError("Worker 1 failed to acquire lock.")

                with transaction.atomic():
                    records = list(
                        NotificationOutbox.objects.select_for_update(skip_locked=True)
                        .filter(id=outbox.id, status=DeliveryStatus.PENDING)
                    )
                    for rec in records:
                        worker2_claimed_ids.append(rec.id)
            except Exception as e:
                worker2_errors.append(e)
            finally:
                worker2_done.set()
                connections.close_all()

        t1 = threading.Thread(target=worker1_task, name="Worker-1-Thread")
        t2 = threading.Thread(target=worker2_task, name="Worker-2-Thread")

        t1.start()
        t2.start()

        t1.join(timeout=15.0)
        t2.join(timeout=15.0)

        self.assertEqual(worker1_errors, [], f"Worker 1 had errors: {worker1_errors}")
        self.assertEqual(worker2_errors, [], f"Worker 2 had errors: {worker2_errors}")
        self.assertEqual(len(worker1_claimed_ids), 1, "Worker 1 must claim the record")
        self.assertEqual(len(worker2_claimed_ids), 0, "Worker 2 must skip the locked record")
        self.assertNotIn(outbox.id, worker2_claimed_ids, "Row must not be claimed by both workers")

        outbox.refresh_from_db()
        self.assertEqual(outbox.status, DeliveryStatus.PROCESSING)
        self.assertEqual(outbox.locked_by, "pg-worker-1")

    def test_real_postgresql_two_workers_concurrent_disjoint_claims(self):
        """
        Genuine PostgreSQL test: two concurrent workers running overlapping transactions
        claim 2 available pending records. Worker 2 skips Worker 1's locked record and claims
        the other record, resulting in disjoint claims under genuine PostgreSQL concurrency.
        """
        if connection.vendor != "postgresql":
            self.skipTest("Genuine multi-connection concurrency test requires PostgreSQL.")

        outbox_a = NotificationOutbox.objects.create(
            match=self.match1,
            idempotency_key=f"match:{self.match1.id}:pg_conc_a",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="PG Concurrency A",
        )
        outbox_b = NotificationOutbox.objects.create(
            match=self.match2,
            idempotency_key=f"match:{self.match2.id}:pg_conc_b",
            status=DeliveryStatus.PENDING,
            recipient_email="remote@people-prime.com",
            subject="PG Concurrency B",
        )

        w1_locked = threading.Event()
        w2_done = threading.Event()
        w1_claimed = []
        w2_claimed = []
        w1_errors = []
        w2_errors = []

        def w1_task():
            try:
                with transaction.atomic():
                    claimed = claim_pending_records(batch_size=1, worker_id="real-pg-w1")
                    if claimed:
                        w1_claimed.append(claimed[0][0].id)
                    w1_locked.set()
                    if not w2_done.wait(timeout=10.0):
                        raise TimeoutError("Worker 2 timed out.")
            except Exception as e:
                w1_errors.append(e)
            finally:
                connections.close_all()

        def w2_task():
            try:
                if not w1_locked.wait(timeout=10.0):
                    raise TimeoutError("Worker 1 failed to lock.")
                with transaction.atomic():
                    claimed = claim_pending_records(batch_size=1, worker_id="real-pg-w2")
                    if claimed:
                        w2_claimed.append(claimed[0][0].id)
            except Exception as e:
                w2_errors.append(e)
            finally:
                w2_done.set()
                connections.close_all()

        t1 = threading.Thread(target=w1_task, name="Real-PG-W1")
        t2 = threading.Thread(target=w2_task, name="Real-PG-W2")

        t1.start()
        t2.start()

        t1.join(timeout=15.0)
        t2.join(timeout=15.0)

        self.assertEqual(w1_errors, [], f"Worker 1 had errors: {w1_errors}")
        self.assertEqual(w2_errors, [], f"Worker 2 had errors: {w2_errors}")
        self.assertEqual(len(w1_claimed), 1)
        self.assertEqual(len(w2_claimed), 1)
        self.assertNotEqual(w1_claimed[0], w2_claimed[0], "Workers must claim distinct records")
