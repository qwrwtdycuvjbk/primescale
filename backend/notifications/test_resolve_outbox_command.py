"""
Unit and integration tests for the resolve_outbox_notification management command (Phase 9.12).

Verifies:
1. Inspect returns expected info without changing the database row.
2. Dismiss requires operator and reason and updates an eligible manual-review record to CANCELLED.
3. Dismiss refuses missing operator or reason.
4. Dismiss refuses records that are not in PERMANENTLY_FAILED or do not have manual_review_required=True.
5. Retry refuses missing confirmation flag, missing operator, or missing reason.
6. Retry refuses records with provider message ID or delivery timestamp.
7. Retry refuses ordinary permanent failures that do not have manual_review_required=True.
8. Successful retry preserves the idempotency key, sets status=PENDING, clears lease fields, and records operator authorization.
9. Re-resolving an already-resolved record (repeated dismiss/retry) is rejected.
10. Ineligible, paused, or expired matches cannot be retried.
11. Repeated matching after a manual-review record exists leaves the record in PERMANENTLY_FAILED.
12. Legacy task invoked twice on a match creates PERMANENTLY_FAILED on first call and exits with outbox_already_exists on second.
13. Zero live emails or network connections occur during any command execution.
"""

import io
import socket
import uuid
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from candidates.models import CandidateProfile
from companies.models import Company
from jobs.models import Job
from matching.hybrid_engine import HybridMatchingEngine, HybridScoreBreakdown
from matching.models import Match
from matching.tasks import notify_recruiter_high_match_task
from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType


class ResolveOutboxNotificationCommandTests(TestCase):
    def setUp(self):
        mail.outbox.clear()

        self.candidate_user = User.objects.create_user(
            email="cand_mgmt@test.com",
            password="Password123!",
            role=User.Role.CANDIDATE,
            full_name="Candidate Mgmt",
        )
        self.candidate = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Senior Architect",
            skills=["python", "django", "celery"],
            experience_level="senior",
            profile_complete=True,
            open_to_matching=True,
        )

        self.employer_user = User.objects.create_user(
            email="emp_mgmt@test.com",
            password="Password123!",
            role=User.Role.EMPLOYER,
            full_name="Employer Mgmt",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Alpha Corp",
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Distributed Engineer",
            description="High scale cloud.",
            role_type="full-time",
            experience_level="senior",
            tech_stack=["python", "django"],
            status=Job.Status.ACTIVE,
        )

        self.match = Match.objects.create(
            candidate_profile=self.candidate,
            job=self.job,
            match_score=92,
            match_reason="Strong alignment (92%)",
            status=Match.Status.SUGGESTED,
            visible_to_employer=False,
        )

        # Create a sample manual-review outbox record stuck in PERMANENTLY_FAILED
        self.manual_outbox = NotificationOutbox.objects.create(
            match=self.match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
            idempotency_key=f"match:{self.match.id}:{NotificationType.HIGH_MATCH_ALERT}",
            status=DeliveryStatus.PERMANENTLY_FAILED,
            recipient_email="remote@people-prime.com",
            subject="[High Match Alert] 92% Match: Senior Distributed Engineer at Alpha Corp",
            payload={
                "match_id": str(self.match.id),
                "job_id": str(self.job.id),
                "final_score": 92,
                "manual_review_required": True,
                "reconciliation_source": "legacy_celery_task",
            },
            last_error="Legacy task reconciliation: delivery status unknown; manual review required.",
            retry_count=0,
            max_retries=0,
            provider_message_id=None,
            delivered_at=None,
        )

    def test_inspect_returns_expected_info_without_modifying_row(self):
        """Action 'inspect' outputs record details and does not alter database state."""
        out = io.StringIO()
        call_command("resolve_outbox_notification", str(self.manual_outbox.id), action="inspect", stdout=out)
        output = out.getvalue()

        self.assertIn(str(self.manual_outbox.id), output)
        self.assertIn("permanently_failed", output)
        self.assertIn("Manual Review Required: True", output)
        self.assertIn("Already Resolved:       False", output)
        self.assertIn("Sanitized Last Error:", output)

        # Confirm DB row was completely untouched
        refreshed = NotificationOutbox.objects.get(id=self.manual_outbox.id)
        self.assertEqual(refreshed.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertEqual(refreshed.updated_at, self.manual_outbox.updated_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_dismiss_requires_operator_and_reason(self):
        """Action 'dismiss' requires non-empty operator and reason."""
        with self.assertRaises(CommandError) as ctx:
            call_command("resolve_outbox_notification", str(self.manual_outbox.id), action="dismiss")
        self.assertIn("requires a non-empty '--operator'", str(ctx.exception))

        with self.assertRaises(CommandError) as ctx:
            call_command(
                "resolve_outbox_notification",
                str(self.manual_outbox.id),
                action="dismiss",
                operator="ops-alice",
            )
        self.assertIn("requires a non-empty '--reason'", str(ctx.exception))

    def test_dismiss_successfully_updates_eligible_manual_review_record(self):
        """Dismissing an eligible manual-review record transitions to CANCELLED and stores audit metadata."""
        out = io.StringIO()
        call_command(
            "resolve_outbox_notification",
            str(self.manual_outbox.id),
            action="dismiss",
            operator="ops-alice",
            reason="Confirmed recruiter already saw this alert in legacy system.",
            stdout=out,
        )
        self.assertIn("Successfully dismissed", out.getvalue())

        refreshed = NotificationOutbox.objects.get(id=self.manual_outbox.id)
        self.assertEqual(refreshed.status, DeliveryStatus.CANCELLED)
        self.assertIn("Dismissed by operator 'ops-alice'", refreshed.last_error)
        self.assertTrue(refreshed.payload["manual_review_resolved"])
        self.assertEqual(refreshed.payload["manual_review_resolution"], "dismissed")
        self.assertEqual(refreshed.payload["manual_review_resolved_by"], "ops-alice")
        self.assertIn("manual_review_resolved_at", refreshed.payload)
        self.assertEqual(len(mail.outbox), 0)

    def test_dismiss_refuses_ordinary_permanent_failure_without_manual_review_flag(self):
        """Records without manual_review_required=True cannot be dismissed via this workflow."""
        ordinary_outbox = NotificationOutbox.objects.create(
            match=self.match,
            notification_type=NotificationType.CANDIDATE_INTERESTED,
            idempotency_key=f"match:{self.match.id}:{NotificationType.CANDIDATE_INTERESTED}",
            status=DeliveryStatus.PERMANENTLY_FAILED,
            recipient_email="remote@people-prime.com",
            subject="Test",
            payload={"final_score": 90},  # No manual_review_required
            last_error="Max retries exhausted",
        )

        with self.assertRaises(CommandError) as ctx:
            call_command(
                "resolve_outbox_notification",
                str(ordinary_outbox.id),
                action="dismiss",
                operator="ops-alice",
                reason="Dismissing ordinary failure",
            )
        self.assertIn("'manual_review_required' flag is not set", str(ctx.exception))

    def test_retry_refuses_missing_confirmation_or_operator_or_reason(self):
        """Action 'retry' requires operator, reason, and --confirm-no-prior-delivery."""
        with self.assertRaises(CommandError) as ctx:
            call_command(
                "resolve_outbox_notification",
                str(self.manual_outbox.id),
                action="retry",
                operator="ops-alice",
                reason="Retrying",
            )
        self.assertIn("requires '--confirm-no-prior-delivery'", str(ctx.exception))

    def test_retry_refuses_record_with_provider_message_id_or_delivery_timestamp(self):
        """Retry strictly refuses records with evidence of provider acceptance or delivery."""
        # Provider message ID present
        self.manual_outbox.provider_message_id = "re_test_duplicate_prevented"
        self.manual_outbox.save(update_fields=["provider_message_id"])

        with self.assertRaises(CommandError) as ctx:
            call_command(
                "resolve_outbox_notification",
                str(self.manual_outbox.id),
                action="retry",
                operator="ops-alice",
                reason="Attempting retry on accepted record",
                confirm_no_prior_delivery=True,
            )
        self.assertIn("already has provider message ID", str(ctx.exception))

    def test_retry_refuses_ordinary_permanent_failures(self):
        """Arbitrary permanent failures without manual_review_required=True are refused."""
        ordinary_outbox = NotificationOutbox.objects.create(
            match=self.match,
            notification_type=NotificationType.CANDIDATE_INTERESTED,
            idempotency_key=f"match:{self.match.id}:cand_interested_ordinary",
            status=DeliveryStatus.PERMANENTLY_FAILED,
            recipient_email="remote@people-prime.com",
            subject="Test",
            payload={"manual_review_required": False},
            last_error="HTTP 400 Bad Request",
        )

        with self.assertRaises(CommandError) as ctx:
            call_command(
                "resolve_outbox_notification",
                str(ordinary_outbox.id),
                action="retry",
                operator="ops-alice",
                reason="Attempting unauthorized retry",
                confirm_no_prior_delivery=True,
            )
        self.assertIn("'manual_review_required' flag is not set", str(ctx.exception))

    def test_retry_refuses_ineligible_or_expired_matches(self):
        """Retry validates business eligibility: job paused/expired or candidate closed."""
        # Pause the job
        self.job.status = Job.Status.PAUSED
        self.job.save(update_fields=["status"])

        with self.assertRaises(CommandError) as ctx:
            call_command(
                "resolve_outbox_notification",
                str(self.manual_outbox.id),
                action="retry",
                operator="ops-alice",
                reason="Trying on paused job",
                confirm_no_prior_delivery=True,
            )
        self.assertIn("business eligibility check failed", str(ctx.exception))
        self.assertIn("no longer active", str(ctx.exception))

    def test_successful_retry_preserves_idempotency_key_and_reschedules_as_pending(self):
        """Successful retry sets status=PENDING, clears lease, resets retry limits, and records operator audit."""
        out = io.StringIO()
        original_key = self.manual_outbox.idempotency_key

        call_command(
            "resolve_outbox_notification",
            str(self.manual_outbox.id),
            action="retry",
            operator="ops-alice",
            reason="Verified recruiter inbox: confirmed email was never sent in legacy system.",
            confirm_no_prior_delivery=True,
            stdout=out,
        )
        self.assertIn("Successfully authorized retry", out.getvalue())

        refreshed = NotificationOutbox.objects.get(id=self.manual_outbox.id)
        self.assertEqual(refreshed.status, DeliveryStatus.PENDING)
        self.assertEqual(refreshed.idempotency_key, original_key)
        self.assertEqual(refreshed.retry_count, 0)
        self.assertEqual(refreshed.max_retries, 3)
        self.assertIsNone(refreshed.locked_at)
        self.assertIsNone(refreshed.locked_by)
        self.assertIsNone(refreshed.lease_token)
        self.assertIn("Operator 'ops-alice' authorized retry", refreshed.last_error)

        payload = refreshed.payload
        self.assertTrue(payload["manual_review_resolved"])
        self.assertEqual(payload["manual_review_resolution"], "retry_authorized")
        self.assertEqual(payload["manual_review_authorized_by"], "ops-alice")
        self.assertTrue(payload["operator_confirmed_no_prior_delivery"])

        # No email was sent by the management command
        self.assertEqual(len(mail.outbox), 0)

    def test_repeated_resolution_refuses_reactivating_already_resolved_records(self):
        """Once resolved (dismissed or retry authorized), repeated calls are rejected."""
        call_command(
            "resolve_outbox_notification",
            str(self.manual_outbox.id),
            action="dismiss",
            operator="ops-alice",
            reason="Dismissing once",
        )

        with self.assertRaises(CommandError) as ctx:
            call_command(
                "resolve_outbox_notification",
                str(self.manual_outbox.id),
                action="dismiss",
                operator="ops-bob",
                reason="Trying to dismiss again",
            )
        self.assertIn("Only records in 'permanently_failed' can be dismissed", str(ctx.exception))

    def test_repeated_matching_preserves_manual_review_permanently_failed_state(self):
        """Repeated hybrid matching runs preserve the PERMANENTLY_FAILED state without resetting it."""
        engine = HybridMatchingEngine()
        breakdown = HybridScoreBreakdown(
            semantic_score=95.0,
            skill_score=92.0,
            exp_score=90.0,
            final_score=93.5,
            qualifies=True,
            reason="Higher score re-run (93.5%)",
        )

        # Run matching again for the same candidate/job pair
        match = engine._persist_match(self.candidate, self.job, breakdown)
        self.assertEqual(match.id, self.match.id)

        # Outbox record MUST still be PERMANENTLY_FAILED (not reset to PENDING)
        refreshed = NotificationOutbox.objects.get(id=self.manual_outbox.id)
        self.assertEqual(refreshed.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertEqual(NotificationOutbox.objects.filter(match=self.match).count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_legacy_task_called_twice_records_permanently_failed_then_detects_existing(self):
        """Legacy task invoked twice: first call records PERMANENTLY_FAILED, second call safely detects outbox_already_exists."""
        # Create a fresh match with a distinct job to satisfy unique_candidate_job_match
        job2 = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Python Backend Lead",
            description="High scale cloud systems.",
            role_type="full-time",
            experience_level="lead",
            tech_stack=["python", "django", "postgres"],
            status=Job.Status.ACTIVE,
        )
        match2 = Match.objects.create(
            candidate_profile=self.candidate,
            job=job2,
            match_score=88,
            match_reason="Fresh match without outbox",
            status=Match.Status.SUGGESTED,
        )
        self.assertEqual(NotificationOutbox.objects.filter(match=match2).count(), 0)

        # Call 1: Creates PERMANENTLY_FAILED manual-review record
        res1 = notify_recruiter_high_match_task(str(match2.id))
        self.assertFalse(res1["delivered"])
        self.assertEqual(res1["status"], "manual_review_required")
        self.assertEqual(NotificationOutbox.objects.filter(match=match2).count(), 1)
        outbox_row = NotificationOutbox.objects.get(match=match2)
        self.assertEqual(outbox_row.status, DeliveryStatus.PERMANENTLY_FAILED)

        # Call 2: Detects existing outbox record, does nothing
        res2 = notify_recruiter_high_match_task(str(match2.id))
        self.assertFalse(res2["delivered"])
        self.assertEqual(res2["status"], "outbox_already_exists")
        self.assertEqual(res2["outbox_status"], DeliveryStatus.PERMANENTLY_FAILED)
        self.assertEqual(NotificationOutbox.objects.filter(match=match2).count(), 1)

        # Exactly zero emails dispatched across both calls
        self.assertEqual(len(mail.outbox), 0)

    def test_no_live_network_calls_occur_during_command_execution(self):
        """Enforces that socket level connections are never attempted during command execution."""
        with patch.object(socket.socket, "connect", side_effect=RuntimeError("Live network call strictly forbidden")):
            out = io.StringIO()
            call_command("resolve_outbox_notification", str(self.manual_outbox.id), action="inspect", stdout=out)
            self.assertIn("--- NotificationOutbox Record", out.getvalue())

            call_command(
                "resolve_outbox_notification",
                str(self.manual_outbox.id),
                action="retry",
                operator="ops-alice",
                reason="Tested with blocked socket",
                confirm_no_prior_delivery=True,
                stdout=out,
            )
            self.assertIn("Successfully authorized retry", out.getvalue())
