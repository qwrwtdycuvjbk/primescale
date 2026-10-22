"""
Transactional Notification Outbox Integration Tests (Phase 9.1).

Verifies:
1. Qualifying score of 85 creates exactly one outbox record.
2. Score below 85 creates no high-match alert.
3. Score above 85 creates the correct payload and recipient.
4. Match transaction rollback also rolls back its outbox record.
5. Repeated matching runs do not create duplicate alerts.
6. Existing Match status and visibility are preserved.
7. Concurrent creation or uniqueness conflicts are handled safely.
8. Payload validation rejects prohibited sensitive fields.
9. No email client or network call is invoked.
10. Transactional boundaries and real database rollbacks.
"""

import socket
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from candidates.models import CandidateProfile
from companies.models import Company
from jobs.models import Job
from matching.hybrid_engine import (
    HIGH_MATCH_ALERT_THRESHOLD,
    HybridMatchingEngine,
    HybridScoreBreakdown,
    calculate_hybrid_score,
)
from matching.models import Match
from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType
from notifications.services import (
    create_high_match_outbox_record,
    validate_outbox_payload,
)

User = get_user_model()


class OutboxPayloadValidationTests(TestCase):
    """Test payload validation rejects prohibited sensitive fields and vectors."""

    def test_valid_payload_accepted(self):
        valid = {
            "match_id": "e4f8d689-53e7-4950-8b01-13c5448386a3",
            "job_id": "2706dbf4-fc12-40f4-8848-bc61a0077c5c",
            "job_title": "Senior Python Engineer",
            "company_name": "Acme Corp",
            "final_score": 90,
            "raw_final_score": 89.75,
            "score_breakdown": {
                "semantic_score": 95.0,
                "skill_score": 85.0,
                "experience_score": 80.0,
            },
        }
        # Should not raise
        validate_outbox_payload(valid)

    def test_prohibited_resume_content_rejected(self):
        invalid = {
            "match_id": "123",
            "resume_text": "Experienced engineer with 10 years experience...",
        }
        with self.assertRaises(ValueError) as cm:
            validate_outbox_payload(invalid)
        self.assertIn("Prohibited", str(cm.exception))

    def test_prohibited_vector_array_rejected(self):
        invalid = {
            "match_id": "123",
            "embedding": [0.1] * 2048,
        }
        with self.assertRaises(ValueError) as cm:
            validate_outbox_payload(invalid)
        self.assertIn("Prohibited", str(cm.exception))

    def test_prohibited_phone_number_rejected(self):
        invalid = {
            "match_id": "123",
            "candidate_phone": "+1-555-0199",
        }
        with self.assertRaises(ValueError) as cm:
            validate_outbox_payload(invalid)
        self.assertIn("Prohibited personal contact key", str(cm.exception))

    def test_prohibited_credentials_rejected(self):
        for prohibited_key in ["api_key", "secret_token", "user_password"]:
            invalid = {"match_id": "123", prohibited_key: "secret123"}
            with self.assertRaises(ValueError) as cm:
                validate_outbox_payload(invalid)
            self.assertIn("Prohibited sensitive key", str(cm.exception))

    def test_prohibited_long_text_blob_rejected(self):
        invalid = {
            "match_id": "123",
            "raw_dump": "A" * 501,
        }
        with self.assertRaises(ValueError) as cm:
            validate_outbox_payload(invalid)
        self.assertIn("Prohibited long text blob", str(cm.exception))


class OutboxTransactionalIntegrationTests(TestCase):
    """
    Integration tests for transactional outbox creation via HybridMatchingEngine._persist_match.
    """

    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="employer_outbox@test.com", password="Password123!", role=User.Role.EMPLOYER
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Prime Tech Solutions",
            description="Leading AI Solutions",
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Lead Cloud Architect",
            description="Design scalable cloud platforms",
            role_type="full-time",
            experience_level="lead",
            status=Job.Status.ACTIVE,
        )

        self.candidate_user = User.objects.create_user(
            email="candidate_outbox@test.com", password="Password123!", role=User.Role.CANDIDATE
        )
        self.candidate = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Principal Cloud Architect",
            skills=["aws", "python", "kubernetes", "terraform"],
            experience_level="lead",
            open_to_matching=True,
            profile_complete=True,
        )

    def test_qualifying_score_85_creates_exactly_one_outbox_record(self):
        """A qualifying score of exactly 85 creates exactly one outbox record in PENDING status."""
        breakdown_85 = calculate_hybrid_score(85.0, 85.0, 85.0)
        self.assertEqual(breakdown_85.final_score, 85.0)

        match = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_85)

        # Match verification
        self.assertEqual(match.match_score, 85)
        self.assertIsNotNone(match.recruiter_notified_at)
        self.assertFalse(match.visible_to_employer)

        # Outbox verification
        outbox_records = NotificationOutbox.objects.filter(match=match)
        self.assertEqual(outbox_records.count(), 1)

        outbox = outbox_records.first()
        self.assertEqual(outbox.notification_type, NotificationType.HIGH_MATCH_ALERT)
        self.assertEqual(outbox.status, DeliveryStatus.PENDING)
        self.assertEqual(outbox.idempotency_key, f"match:{match.id}:{NotificationType.HIGH_MATCH_ALERT}")
        self.assertEqual(outbox.recipient_email, getattr(settings, "PEOPLE_PRIME_HANDOFF_EMAIL", "remote@people-prime.com"))

    def test_score_below_85_creates_no_high_match_alert(self):
        """Scores strictly below 85.0 (e.g. 84.8 or 75.0) create NO outbox record."""
        # 84.8 rounds to 85, but unrounded is < 85.0
        breakdown_sub85 = calculate_hybrid_score(84.8, 84.8, 84.8)
        self.assertEqual(breakdown_sub85.final_score, 84.8)

        match = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_sub85)
        self.assertIsNone(match.recruiter_notified_at)
        self.assertEqual(NotificationOutbox.objects.filter(match=match).count(), 0)

        # 75.0 qualifying for match, but well below 85
        breakdown_75 = calculate_hybrid_score(75.0, 75.0, 75.0)
        match_75 = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_75)
        self.assertIsNone(match_75.recruiter_notified_at)
        self.assertEqual(NotificationOutbox.objects.filter(match=match_75).count(), 0)

    def test_score_above_85_creates_correct_payload_and_recipient(self):
        """Scores above 85 create correctly formatted payload with score breakdown."""
        breakdown_93 = calculate_hybrid_score(96.0, 90.0, 90.0)  # 48.0 + 27.0 + 18.0 = 93.0
        self.assertEqual(breakdown_93.final_score, 93.0)

        match = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_93)
        outbox = NotificationOutbox.objects.get(match=match, notification_type=NotificationType.HIGH_MATCH_ALERT)

        expected_recipient = getattr(settings, "PEOPLE_PRIME_HANDOFF_EMAIL", "remote@people-prime.com")
        self.assertEqual(outbox.recipient_email, expected_recipient)
        self.assertIn("Lead Cloud Architect", outbox.subject)
        self.assertIn("Prime Tech Solutions", outbox.subject)

        payload = outbox.payload
        self.assertEqual(payload["match_id"], str(match.id))
        self.assertEqual(payload["job_id"], str(self.job.id))
        self.assertEqual(payload["job_title"], "Lead Cloud Architect")
        self.assertEqual(payload["company_name"], "Prime Tech Solutions")
        self.assertEqual(payload["final_score"], 93)
        self.assertEqual(payload["raw_final_score"], 93.0)
        self.assertEqual(payload["score_breakdown"]["semantic_score"], 96.0)
        self.assertEqual(payload["score_breakdown"]["skill_score"], 90.0)
        self.assertEqual(payload["score_breakdown"]["experience_score"], 90.0)

    def test_repeated_matching_runs_do_not_create_duplicate_alerts(self):
        """Multiple matching runs for the same qualifying pair do NOT duplicate outbox records."""
        breakdown_88 = calculate_hybrid_score(88.0, 88.0, 88.0)
        match1 = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_88)
        self.assertEqual(NotificationOutbox.objects.filter(match=match1).count(), 1)

        # Second matching run with slight score change
        breakdown_89 = calculate_hybrid_score(89.0, 89.0, 89.0)
        match2 = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_89)
        self.assertEqual(match2.id, match1.id)
        self.assertEqual(NotificationOutbox.objects.filter(match=match1).count(), 1)

        # Third matching run
        breakdown_91 = calculate_hybrid_score(91.0, 91.0, 91.0)
        match3 = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_91)
        self.assertEqual(NotificationOutbox.objects.filter(match=match1).count(), 1)

    def test_existing_match_status_and_visibility_preserved(self):
        """Preserves candidate action states and employer visibility when outbox record is added."""
        existing_match = Match.objects.create(
            candidate_profile=self.candidate,
            job=self.job,
            match_score=80,
            status=Match.Status.CANDIDATE_INTERESTED,
            visible_to_employer=True,
        )

        breakdown_86 = calculate_hybrid_score(86.0, 86.0, 86.0)
        updated_match = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_86)

        self.assertEqual(updated_match.id, existing_match.id)
        self.assertEqual(updated_match.status, Match.Status.CANDIDATE_INTERESTED)
        self.assertTrue(updated_match.visible_to_employer)
        self.assertEqual(updated_match.match_score, 86)
        self.assertIsNotNone(updated_match.recruiter_notified_at)

        # Outbox record created because score transitioned to >= 85
        self.assertEqual(NotificationOutbox.objects.filter(match=updated_match).count(), 1)

    def test_no_email_client_or_network_call_is_invoked(self):
        """Writing outbox records strictly defers email dispatch; no network calls occur."""
        with patch("notifications.client.ResendHTTPClient.send_email") as mock_send, \
             patch.object(socket.socket, "connect", side_effect=RuntimeError("Network forbidden")):
            breakdown_90 = calculate_hybrid_score(90.0, 90.0, 90.0)
            match = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_90)

            # Outbox record exists in PENDING state
            outbox = NotificationOutbox.objects.get(match=match)
            self.assertEqual(outbox.status, DeliveryStatus.PENDING)

            # Email dispatch client was NOT invoked
            mock_send.assert_not_called()


class OutboxRollbackAndConcurrencyTests(TransactionTestCase):
    """
    Transaction-level rollback and concurrency tests using real PostgreSQL transactions.
    """

    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="emp_tx@test.com", password="Password123!", role=User.Role.EMPLOYER
        )
        self.company = Company.objects.create(name="Concurrency Labs", owner=self.employer_user)
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Systems Engineer",
            description="Systems engineering",
            role_type="full-time",
            experience_level="senior",
            status=Job.Status.ACTIVE,
        )
        self.candidate_user = User.objects.create_user(
            email="cand_tx@test.com", password="Password123!", role=User.Role.CANDIDATE
        )
        self.candidate = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Senior Systems Engineer",
            skills=["c++", "linux", "python"],
            experience_level="senior",
            open_to_matching=True,
            profile_complete=True,
        )

    def test_match_transaction_rollback_also_rolls_back_outbox_record(self):
        """
        Verifies atomic rollback: if an exception rolls back the Match creation transaction,
        the associated NotificationOutbox record is also rolled back.
        """
        breakdown_90 = calculate_hybrid_score(90.0, 90.0, 90.0)

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                match = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown_90)
                # Verify match and outbox exist inside the uncommitted transaction
                self.assertTrue(Match.objects.filter(candidate_profile=self.candidate, job=self.job).exists())
                self.assertTrue(NotificationOutbox.objects.filter(match=match).exists())
                # Trigger transaction rollback
                raise RuntimeError("Simulated transaction rollback")

        # After rollback: neither Match nor NotificationOutbox must exist
        self.assertFalse(
            Match.objects.filter(candidate_profile=self.candidate, job=self.job).exists(),
            "Match record MUST NOT persist after transaction rollback."
        )
        self.assertEqual(
            NotificationOutbox.objects.filter(match__candidate_profile=self.candidate, match__job=self.job).count(),
            0,
            "NotificationOutbox record MUST NOT persist after transaction rollback."
        )

    def test_concurrent_outbox_creation_conflict_handled_safely(self):
        """
        Verifies that when a concurrent worker inserts the outbox record first,
        the inner savepoint catches IntegrityError and retrieves the winning record
        without corrupting the outer transaction.
        """
        match = Match.objects.create(
            candidate_profile=self.candidate,
            job=self.job,
            match_score=90,
            status=Match.Status.SUGGESTED,
        )
        breakdown_90 = calculate_hybrid_score(90.0, 90.0, 90.0)

        # Pre-create winning outbox record (Worker 1)
        winning_outbox = create_high_match_outbox_record(match, self.job, breakdown_90)
        self.assertIsNotNone(winning_outbox)
        self.assertEqual(NotificationOutbox.objects.filter(match=match).count(), 1)

        # Worker 2 attempts creation where IntegrityError is raised
        with patch.object(NotificationOutbox.objects, "create", side_effect=IntegrityError("duplicate key")):
            second_outbox = create_high_match_outbox_record(match, self.job, breakdown_90)

        self.assertEqual(second_outbox.id, winning_outbox.id)
        self.assertEqual(NotificationOutbox.objects.filter(match=match).count(), 1)
