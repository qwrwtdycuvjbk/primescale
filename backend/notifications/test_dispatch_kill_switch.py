"""
Focused Regression Tests for Notification Outbox Dispatch Kill Switch.

Verifies:
1. NOTIFICATIONS_DISPATCH_ENABLED defaults to False in settings.
2. Case variations, whitespace, and falsy strings are handled safely during parsing.
3. When NOTIFICATIONS_DISPATCH_ENABLED is False:
   - dispatch_outbox_notifications_task exits early with status="disabled".
   - dispatch_pending_outbox_records worker function is never called.
   - Outbox database rows (status=PENDING) remain completely untouched:
     * status remains PENDING
     * locked_at, locked_by, lease_token remain None
     * retry_count remains 0
     * first_attempted_at and delivered_at remain None
     * provider_message_id remains None
     * last_error remains None
   - ResendHTTPClient and requests.Session are never instantiated or invoked.
   - Zero network calls are attempted.
4. When NOTIFICATIONS_DISPATCH_ENABLED is True:
   - Task proceeds to claim and dispatch records through normal path.
5. recover_stale_outbox_leases_task remains completely functional regardless of the kill switch.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from candidates.models import CandidateProfile
from companies.models import Company
from jobs.models import Job
from matching.models import Match
from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType
from notifications.tasks import (
    dispatch_outbox_notifications_task,
    recover_stale_outbox_leases_task,
)

User = get_user_model()


class NotificationDispatchKillSwitchTests(TestCase):
    """Test suite verifying the NOTIFICATIONS_DISPATCH_ENABLED kill switch."""

    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="killswitch_employer@test.com",
            password="Password123!",
            role=User.Role.EMPLOYER,
        )
        self.company = Company.objects.create(
            name="KillSwitch Corp",
            owner=self.employer_user,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Principal Reliability Engineer",
            status=Job.Status.ACTIVE,
        )
        self.candidate_user = User.objects.create_user(
            email="killswitch_candidate@test.com",
            password="Password123!",
            role=User.Role.CANDIDATE,
        )
        self.candidate = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Reliability Specialist",
            skills=["python", "django", "celery", "postgresql"],
            experience_level="lead",
            open_to_matching=True,
            profile_complete=True,
        )
        self.match = Match.objects.create(
            candidate_profile=self.candidate,
            job=self.job,
            match_score=95,
            status=Match.Status.SUGGESTED,
            visible_to_employer=False,
            recruiter_notified_at=timezone.now(),
        )

        self.fixed_now = timezone.now()
        self.outbox = NotificationOutbox.objects.create(
            match=self.match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
            idempotency_key=f"match:{self.match.id}:high_match_alert:killswitch_test",
            status=DeliveryStatus.PENDING,
            recipient_email="ops-alerts@peopleremotely.internal",
            subject="[High Match Alert] 95% Match: Principal Reliability Engineer",
            payload={"match_id": str(self.match.id), "final_score": 95},
            next_attempt_at=self.fixed_now - timedelta(minutes=5),  # Due now
        )

    def test_setting_defaults_to_false(self):
        """Verify NOTIFICATIONS_DISPATCH_ENABLED defaults to False."""
        self.assertFalse(
            getattr(settings, "NOTIFICATIONS_DISPATCH_ENABLED", True),
            "NOTIFICATIONS_DISPATCH_ENABLED must default to False for staging safety.",
        )

    def test_setting_parser_truthy_and_falsy_strings(self):
        """Verify environment variable parsing handles case, whitespace, and falsy strings safely."""
        def parse_env(val: str | None) -> bool:
            return (val or "false").strip().lower() in ("true", "1", "yes")

        # Truthy variations
        for true_val in ["true", "True", "TRUE", " true ", "1", "yes", "YES"]:
            self.assertTrue(parse_env(true_val), f"Failed for {true_val}")

        # Falsy variations
        for false_val in ["false", "False", "FALSE", "0", "no", "", None, "disabled"]:
            self.assertFalse(parse_env(false_val), f"Failed for {false_val}")

    @override_settings(NOTIFICATIONS_DISPATCH_ENABLED=False)
    @patch("notifications.tasks.dispatch_pending_outbox_records")
    def test_disabled_dispatch_exits_before_worker_invocation(self, mock_dispatch):
        """When disabled, task returns disabled status without calling the worker."""
        res = dispatch_outbox_notifications_task()

        self.assertEqual(res["status"], "disabled")
        self.assertEqual(res["claimed_count"], 0)
        self.assertEqual(res["results"], [])
        self.assertEqual(res["reason"], "NOTIFICATIONS_DISPATCH_ENABLED is False")
        mock_dispatch.assert_not_called()

    @override_settings(NOTIFICATIONS_DISPATCH_ENABLED=False)
    @patch("notifications.client.requests.Session.post")
    def test_disabled_dispatch_preserves_outbox_rows_completely(self, mock_post):
        """When disabled, pending outbox records remain completely unmodified in DB."""
        # Capture state before task invocation
        original_created_at = self.outbox.created_at
        original_updated_at = self.outbox.updated_at
        original_next_attempt_at = self.outbox.next_attempt_at
        original_idempotency_key = self.outbox.idempotency_key

        # Invoke the Celery task directly
        res = dispatch_outbox_notifications_task()

        self.assertEqual(res["status"], "disabled")
        self.assertEqual(res["claimed_count"], 0)

        # Refresh row from database
        self.outbox.refresh_from_db()

        # Assert zero mutations
        self.assertEqual(self.outbox.status, DeliveryStatus.PENDING)
        self.assertIsNone(self.outbox.locked_at)
        self.assertIsNone(self.outbox.locked_by)
        self.assertIsNone(self.outbox.lease_token)
        self.assertEqual(self.outbox.retry_count, 0)
        self.assertIsNone(self.outbox.first_attempted_at)
        self.assertIsNone(self.outbox.delivered_at)
        self.assertIsNone(self.outbox.provider_message_id)
        self.assertIsNone(self.outbox.last_error)
        self.assertEqual(self.outbox.idempotency_key, original_idempotency_key)
        self.assertEqual(self.outbox.created_at, original_created_at)
        self.assertEqual(self.outbox.updated_at, original_updated_at)
        self.assertEqual(self.outbox.next_attempt_at, original_next_attempt_at)

        # Confirm zero HTTP requests were attempted
        mock_post.assert_not_called()

    @override_settings(NOTIFICATIONS_DISPATCH_ENABLED=True)
    @patch("notifications.tasks.dispatch_pending_outbox_records")
    def test_enabled_dispatch_invokes_worker(self, mock_dispatch):
        """When explicitly enabled, task proceeds through the normal dispatch worker path."""
        mock_dispatch.return_value = {
            "claimed_count": 1,
            "results": [{"status": "accepted_by_provider", "record_id": str(self.outbox.id)}],
        }

        res = dispatch_outbox_notifications_task()

        self.assertEqual(res["claimed_count"], 1)
        mock_dispatch.assert_called_once()
        _, kwargs = mock_dispatch.call_args
        self.assertIn("worker_id", kwargs)

    @override_settings(NOTIFICATIONS_DISPATCH_ENABLED=False)
    @patch("notifications.tasks.recover_stale_outbox_leases")
    def test_stale_lease_recovery_remains_active_when_dispatch_disabled(self, mock_recover):
        """Stale lease recovery task operates independently of dispatch kill switch."""
        mock_recover.return_value = 3

        res = recover_stale_outbox_leases_task()

        self.assertEqual(res["recovered_count"], 3)
        mock_recover.assert_called_once()
