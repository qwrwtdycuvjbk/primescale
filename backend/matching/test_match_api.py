"""
Phase 8 — Candidate/Employer Match Integration and Recruiter Notification Workflow Tests.

Verifies:
1. Candidate match list and detail authorization (cross-candidate isolation).
2. Employer company isolation and membership enforcement.
3. Hidden and unapproved match filtering (visible_to_employer=False is blocked from employers).
4. Score and status serialization (no embeddings or private resume text).
5. Recruiter notification workflow (score >= 85 threshold, idempotency, duplicate prevention, privacy).
6. Matching task orchestration (stale vector rejection, duplicate safety, no bulk runs).
"""

import socket
import uuid
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.services import send_password_reset_email, send_verification_email
from candidates.models import CandidateProfile
from companies.models import Company, CompanyMember
from jobs.models import Job
from matching.hybrid_engine import (
    HIGH_MATCH_ALERT_THRESHOLD,
    HybridMatchingEngine,
    HybridScoreBreakdown,
)
from matching.models import CandidateResumeEmbedding, EmbeddingStatus, JobEmbedding, Match
from matching.services import (
    MIN_MATCH_SCORE,
    notify_recruiters_for_high_match,
    run_hybrid_matching_for_candidate,
    run_hybrid_matching_for_job,
    send_recruiter_high_match_notification,
)
from matching.tasks import notify_recruiter_high_match_task
from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType


class Phase8MatchApiAndAuthorizationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Candidate 1 (Alice)
        self.cand1_user = User.objects.create_user(
            email="alice@test.com",
            password="Password123!",
            role=User.Role.CANDIDATE,
            full_name="Alice Candidate",
        )
        self.cand1_profile = CandidateProfile.objects.create(
            user=self.cand1_user,
            headline="Senior Backend Engineer",
            current_title="Senior Backend Engineer",
            phone="1234567890",
            role_categories=["Engineering"],
            skills=["python", "django", "postgresql"],
            experience_level="senior",
            profile_complete=True,
            open_to_matching=True,
            resume_url="https://example.com/resumes/alice.pdf",
        )

        # Candidate 2 (Bob)
        self.cand2_user = User.objects.create_user(
            email="bob@test.com",
            password="Password123!",
            role=User.Role.CANDIDATE,
            full_name="Bob Candidate",
        )
        self.cand2_profile = CandidateProfile.objects.create(
            user=self.cand2_user,
            headline="Junior Frontend Engineer",
            skills=["react", "javascript"],
            experience_level="junior",
            profile_complete=True,
            open_to_matching=True,
        )

        # Employer 1 (Acme Corp Owner)
        self.emp1_user = User.objects.create_user(
            email="employer1@acme.com",
            password="Password123!",
            role=User.Role.EMPLOYER,
            full_name="Acme Owner",
        )
        self.company1 = Company.objects.create(
            owner=self.emp1_user,
            name="Acme Corp",
            profile_complete=True,
        )
        self.job1 = Job.objects.create(
            company=self.company1,
            posted_by=self.emp1_user,
            title="Senior Backend Developer",
            description="Leading Django API development.",
            role_type="full-time",
            experience_level="senior",
            tech_stack=["python", "django", "postgresql"],
            status=Job.Status.ACTIVE,
        )

        # Employer 1 Team Member (Recruiter at Acme Corp)
        self.emp1_member = User.objects.create_user(
            email="recruiter@acme.com",
            password="Password123!",
            role=User.Role.EMPLOYER,
            full_name="Acme Recruiter",
        )
        CompanyMember.objects.create(
            company=self.company1,
            user=self.emp1_member,
            member_role=CompanyMember.MemberRole.RECRUITER,
        )

        # Employer 2 (Beta Corp Owner - Competitor)
        self.emp2_user = User.objects.create_user(
            email="employer2@beta.com",
            password="Password123!",
            role=User.Role.EMPLOYER,
            full_name="Beta Owner",
        )
        self.company2 = Company.objects.create(
            owner=self.emp2_user,
            name="Beta Corp",
            profile_complete=True,
        )
        self.job2 = Job.objects.create(
            company=self.company2,
            posted_by=self.emp2_user,
            title="Frontend Specialist",
            description="React systems.",
            role_type="full-time",
            experience_level="mid",
            tech_stack=["react", "typescript"],
            status=Job.Status.ACTIVE,
        )

        # Admin User
        self.admin_user = User.objects.create_superuser(
            email="admin@peopleremotely.com",
            password="AdminPassword123!",
            full_name="Global Admin",
        )

    def _auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # =========================================================================
    # Candidate Match Authorization & Experience
    # =========================================================================

    def test_candidate_retrieves_only_authorized_matches(self):
        """Candidate 1 sees their own qualifying matches, never Candidate 2's matches."""
        m1 = Match.objects.create(
            candidate_profile=self.cand1_profile,
            job=self.job1,
            match_score=88,
            match_reason="Strong semantic and skills alignment.",
            status=Match.Status.SUGGESTED,
            visible_to_employer=False,
        )
        m2 = Match.objects.create(
            candidate_profile=self.cand2_profile,
            job=self.job2,
            match_score=92,
            status=Match.Status.SUGGESTED,
            visible_to_employer=False,
        )

        self._auth(self.cand1_user)
        res = self.client.get("/api/v1/matches/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in res.data]
        self.assertIn(str(m1.id), ids)
        self.assertNotIn(str(m2.id), ids)

    def test_candidate_cross_access_forbidden(self):
        """Candidate 1 attempting to access Candidate 2's match detail receives 403 Forbidden."""
        m2 = Match.objects.create(
            candidate_profile=self.cand2_profile,
            job=self.job2,
            match_score=90,
            status=Match.Status.SUGGESTED,
        )

        self._auth(self.cand1_user)
        res = self.client.get(f"/api/v1/matches/{m2.id}/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res_patch = self.client.patch(
            f"/api/v1/matches/{m2.id}/",
            {"status": "candidate_interested"},
            format="json",
        )
        self.assertEqual(res_patch.status_code, status.HTTP_403_FORBIDDEN)

    def test_candidate_subthreshold_match_hidden(self):
        """Matches with score <= 60 are hidden from candidate list and detail endpoints."""
        m_low = Match.objects.create(
            candidate_profile=self.cand1_profile,
            job=self.job1,
            match_score=55,
            status=Match.Status.SUGGESTED,
        )

        self._auth(self.cand1_user)
        res = self.client.get("/api/v1/matches/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in res.data]
        self.assertNotIn(str(m_low.id), ids)

        res_detail = self.client.get(f"/api/v1/matches/{m_low.id}/")
        self.assertEqual(res_detail.status_code, status.HTTP_403_FORBIDDEN)

    def test_candidate_status_update_restrictions(self):
        """Candidate can express interest or reject, but cannot self-shortlist."""
        m = Match.objects.create(
            candidate_profile=self.cand1_profile,
            job=self.job1,
            match_score=85,
            status=Match.Status.SUGGESTED,
        )

        self._auth(self.cand1_user)

        # Tampering: Candidate cannot self-shortlist
        res_tamper = self.client.patch(
            f"/api/v1/matches/{m.id}/",
            {"status": "employer_shortlisted"},
            format="json",
        )
        self.assertEqual(res_tamper.status_code, status.HTTP_403_FORBIDDEN)

        # Valid action: candidate expresses interest
        res_ok = self.client.patch(
            f"/api/v1/matches/{m.id}/",
            {"status": "candidate_interested"},
            format="json",
        )
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ok.data["status"], "candidate_interested")
        m.refresh_from_db()
        self.assertEqual(m.status, Match.Status.CANDIDATE_INTERESTED)

    # =========================================================================
    # Employer Match Authorization & Isolation
    # =========================================================================

    def test_employer_unapproved_matches_hidden(self):
        """Unapproved match (visible_to_employer=False) is NEVER visible in employer list or detail."""
        m_unapproved = Match.objects.create(
            candidate_profile=self.cand1_profile,
            job=self.job1,
            match_score=95,
            status=Match.Status.SUGGESTED,
            visible_to_employer=False,
        )

        # Employer 1 lists matches -> empty
        self._auth(self.emp1_user)
        res = self.client.get("/api/v1/matches/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

        # Employer 1 retrieves detail of unapproved match -> 403 Forbidden
        res_detail = self.client.get(f"/api/v1/matches/{m_unapproved.id}/")
        self.assertEqual(res_detail.status_code, status.HTTP_403_FORBIDDEN)

        # Employer 1 attempts to patch unapproved match -> 403 Forbidden
        res_patch = self.client.patch(
            f"/api/v1/matches/{m_unapproved.id}/",
            {"status": "employer_shortlisted"},
            format="json",
        )
        self.assertEqual(res_patch.status_code, status.HTTP_403_FORBIDDEN)

    def test_employer_company_isolation(self):
        """Employer 2 cannot view or modify Employer 1's company matches."""
        m_approved = Match.objects.create(
            candidate_profile=self.cand1_profile,
            job=self.job1,
            match_score=90,
            status=Match.Status.SUGGESTED,
            visible_to_employer=True,
        )

        # Employer 2 attempts access to Employer 1's match
        self._auth(self.emp2_user)
        res = self.client.get(f"/api/v1/matches/{m_approved.id}/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res_patch = self.client.patch(
            f"/api/v1/matches/{m_approved.id}/",
            {"status": "employer_shortlisted"},
            format="json",
        )
        self.assertEqual(res_patch.status_code, status.HTTP_403_FORBIDDEN)

    def test_employer_company_member_access(self):
        """Company member (recruiter at Acme) has authorized access to company's approved matches."""
        m_approved = Match.objects.create(
            candidate_profile=self.cand1_profile,
            job=self.job1,
            match_score=90,
            status=Match.Status.SUGGESTED,
            visible_to_employer=True,
        )

        self._auth(self.emp1_member)
        res = self.client.get("/api/v1/matches/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

        res_detail = self.client.get(f"/api/v1/matches/{m_approved.id}/")
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)

    def test_serialization_privacy_preservation(self):
        """Serializers never leak raw resume text, normalized text, or embedding vectors."""
        m_approved = Match.objects.create(
            candidate_profile=self.cand1_profile,
            job=self.job1,
            match_score=90,
            match_reason="Hybrid match (90%): Semantic=92%, Skills=90%, Experience=85%",
            status=Match.Status.SUGGESTED,
            visible_to_employer=True,
        )

        # Employer response audit
        self._auth(self.emp1_user)
        res_emp = self.client.get(f"/api/v1/matches/{m_approved.id}/")
        self.assertEqual(res_emp.status_code, status.HTTP_200_OK)
        data_emp = res_emp.data
        self.assertNotIn("embedding", data_emp)
        self.assertNotIn("extracted_text", data_emp)
        self.assertNotIn("normalized_text", data_emp)
        if "candidate_profile" in data_emp and data_emp["candidate_profile"]:
            self.assertNotIn("embedding", data_emp["candidate_profile"])
            self.assertNotIn("extracted_text", data_emp["candidate_profile"])
            self.assertNotIn("resume_url", data_emp["candidate_profile"])
        if "candidate_profiles" in data_emp and data_emp["candidate_profiles"]:
            self.assertNotIn("resume_url", data_emp["candidate_profiles"])

        # Candidate response audit
        self._auth(self.cand1_user)
        res_cand = self.client.get(f"/api/v1/matches/{m_approved.id}/")
        self.assertEqual(res_cand.status_code, status.HTTP_200_OK)
        data_cand = res_cand.data
        self.assertNotIn("embedding", data_cand)
        self.assertNotIn("extracted_text", data_cand)
        self.assertNotIn("recruiter_notified_at", data_cand)

    def test_employer_facing_match_and_serializer_exclude_resume_url(self):
        """
        Phase 10.9: Verify that EmployerCandidateProfileSummarySerializer,
        EmployerMatchSerializer, and employer match/application responses strictly
        omit candidate resume storage keys.
        """
        from matching.serializers import (
            EmployerCandidateProfileSummarySerializer,
            EmployerMatchSerializer,
        )

        # 1. Direct serializer audit
        cand_serializer = EmployerCandidateProfileSummarySerializer(self.cand1_profile)
        self.assertNotIn("resume_url", cand_serializer.data)
        self.assertIn("headline", cand_serializer.data)
        self.assertIn("skills", cand_serializer.data)

        # 2. Approved match employer audit
        m = Match.objects.create(
            candidate_profile=self.cand1_profile,
            job=self.job1,
            match_score=92,
            status=Match.Status.SUGGESTED,
            visible_to_employer=True,
        )
        match_serializer = EmployerMatchSerializer(m)
        self.assertNotIn("resume_url", match_serializer.data["candidate_profile"])
        self.assertNotIn("resume_url", match_serializer.data["candidate_profiles"])

        # 3. Employer match list endpoint audit
        self._auth(self.emp1_user)
        res_list = self.client.get("/api/v1/matches/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        for item in res_list.data:
            if item.get("candidate_profile"):
                self.assertNotIn("resume_url", item["candidate_profile"])
            if item.get("candidate_profiles"):
                self.assertNotIn("resume_url", item["candidate_profiles"])

        # 4. Employer application list endpoint audit
        res_apps = self.client.get("/api/v1/applications/")
        self.assertEqual(res_apps.status_code, status.HTTP_200_OK)
        for item in res_apps.data:
            if item.get("candidate_profile"):
                self.assertNotIn("resume_url", item["candidate_profile"])
            if item.get("candidate_profiles"):
                self.assertNotIn("resume_url", item["candidate_profiles"])

        # 5. Candidate own profile retains resume_url
        self._auth(self.cand1_user)
        res_me = self.client.get("/api/v1/candidates/me/")
        self.assertEqual(res_me.status_code, status.HTTP_200_OK)
        self.assertEqual(res_me.data.get("resume_url"), self.cand1_profile.resume_url)


class Phase910OutboxOnlyNotificationTests(TestCase):
    """
    Phase 9.10 Regression Tests:
    1. A qualifying match (score >= 85) creates one outbox row and schedules no legacy high-match task.
    2. A score below 85 creates no high-match notification.
    3. Repeated matching does not create duplicate outbox rows.
    4. Transaction rollback removes the newly created outbox row.
    5. A legacy task with an existing outbox row does not send an email or create another row.
    6. A legacy task without an outbox row does not automatically send or enqueue an email and produces manual-review signal.
    7. Password-reset and verification emails remain functional under the test email backend.
    8. No tests make live HTTP or SMTP connections.
    """

    def setUp(self):
        cache.clear()
        mail.outbox.clear()

        self.user = User.objects.create_user(
            email="notif_cand@test.com",
            password="Password123!",
            role=User.Role.CANDIDATE,
            full_name="Candidate Alert",
        )
        self.profile = CandidateProfile.objects.create(
            user=self.user,
            headline="Engineer",
            skills=["python"],
            experience_level="mid",
            profile_complete=True,
            open_to_matching=True,
        )
        self.employer = User.objects.create_user(
            email="notif_emp@test.com",
            password="Password123!",
            role=User.Role.EMPLOYER,
            full_name="Employer Alert",
        )
        self.company = Company.objects.create(
            owner=self.employer,
            name="Apex Labs",
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer,
            title="Senior Python Architect",
            description="High scale backend.",
            role_type="full-time",
            experience_level="senior",
            tech_stack=["python", "django"],
            status=Job.Status.ACTIVE,
        )
        self.engine = HybridMatchingEngine()

    def test_qualifying_match_creates_one_outbox_row_and_schedules_no_legacy_task(self):
        """A qualifying match (score >= 85) creates one outbox row and schedules zero legacy Celery tasks."""
        breakdown = HybridScoreBreakdown(
            semantic_score=92.0,
            skill_score=88.0,
            exp_score=85.0,
            final_score=89.6,
            qualifies=True,
            reason="Exceptional alignment (89.6%)",
        )

        with patch("matching.tasks.notify_recruiter_high_match_task.delay") as mock_delay:
            match = self.engine._persist_match(self.profile, self.job, breakdown)

            # Assert outbox row was created in PENDING status
            outbox_records = NotificationOutbox.objects.filter(
                match=match,
                notification_type=NotificationType.HIGH_MATCH_ALERT,
            )
            self.assertEqual(outbox_records.count(), 1)
            outbox = outbox_records.first()
            self.assertEqual(outbox.status, DeliveryStatus.PENDING)
            self.assertEqual(outbox.idempotency_key, f"match:{match.id}:high_match_alert")
            self.assertEqual(outbox.payload["final_score"], 90)
            self.assertEqual(outbox.payload["raw_final_score"], 89.6)

            # Assert legacy task was NEVER scheduled
            mock_delay.assert_not_called()

            # Assert zero emails dispatched via send_mail
            self.assertEqual(len(mail.outbox), 0)

    def test_score_below_85_creates_no_high_match_notification(self):
        """A score below 85 creates zero outbox notifications and schedules zero legacy tasks."""
        breakdown = HybridScoreBreakdown(
            semantic_score=85.0,
            skill_score=85.0,
            exp_score=84.0,
            final_score=84.8,
            qualifies=True,
            reason="Sub-threshold alignment (84.8%)",
        )

        with patch("matching.tasks.notify_recruiter_high_match_task.delay") as mock_delay:
            match = self.engine._persist_match(self.profile, self.job, breakdown)

            # Assert no outbox row exists
            self.assertEqual(
                NotificationOutbox.objects.filter(
                    match=match,
                    notification_type=NotificationType.HIGH_MATCH_ALERT,
                ).count(),
                0,
            )
            mock_delay.assert_not_called()
            self.assertEqual(len(mail.outbox), 0)

    def test_repeated_matching_does_not_create_duplicate_outbox_rows(self):
        """Repeated matching runs do not duplicate outbox rows or overwrite existing statuses."""
        breakdown = HybridScoreBreakdown(
            semantic_score=90.0,
            skill_score=92.0,
            exp_score=90.0,
            final_score=91.0,
            qualifies=True,
            reason="First run (91.0%)",
        )

        # Run 1
        m1 = self.engine._persist_match(self.profile, self.job, breakdown)
        self.assertEqual(
            NotificationOutbox.objects.filter(
                match=m1,
                notification_type=NotificationType.HIGH_MATCH_ALERT,
            ).count(),
            1,
        )

        # Run 2
        breakdown2 = HybridScoreBreakdown(
            semantic_score=94.0,
            skill_score=92.0,
            exp_score=90.0,
            final_score=93.0,
            qualifies=True,
            reason="Second run (93.0%)",
        )
        m2 = self.engine._persist_match(self.profile, self.job, breakdown2)
        self.assertEqual(m1.id, m2.id)

        # Still exactly 1 outbox row
        self.assertEqual(
            NotificationOutbox.objects.filter(
                match=m2,
                notification_type=NotificationType.HIGH_MATCH_ALERT,
            ).count(),
            1,
        )

    def test_transaction_rollback_removes_newly_created_outbox_row(self):
        """If match transaction aborts, the newly created outbox row is rolled back atomically."""
        breakdown = HybridScoreBreakdown(
            semantic_score=88.0,
            skill_score=88.0,
            exp_score=88.0,
            final_score=88.0,
            qualifies=True,
            reason="Rollback test (88.0%)",
        )

        initial_outbox_count = NotificationOutbox.objects.count()

        try:
            with transaction.atomic():
                self.engine._persist_match(self.profile, self.job, breakdown)
                raise RuntimeError("Simulated transaction failure after outbox creation")
        except RuntimeError:
            pass

        # Entire transaction rolled back
        self.assertEqual(NotificationOutbox.objects.count(), initial_outbox_count)

    def test_legacy_task_with_existing_outbox_row_does_not_send_or_duplicate(self):
        """A legacy task with an existing outbox row does not send an email or create another row."""
        breakdown = HybridScoreBreakdown(
            semantic_score=90.0,
            skill_score=90.0,
            exp_score=90.0,
            final_score=90.0,
            qualifies=True,
            reason="Pre-existing outbox (90.0%)",
        )
        match = self.engine._persist_match(self.profile, self.job, breakdown)
        self.assertEqual(NotificationOutbox.objects.filter(match=match).count(), 1)

        # Execute the legacy task
        res = notify_recruiter_high_match_task(str(match.id))

        self.assertFalse(res["delivered"])
        self.assertEqual(res["status"], "outbox_already_exists")
        # Still exactly 1 outbox row
        self.assertEqual(NotificationOutbox.objects.filter(match=match).count(), 1)
        # Zero emails dispatched
        self.assertEqual(len(mail.outbox), 0)

    def test_legacy_task_without_outbox_row_records_manual_review_permanently_failed(self):
        """A legacy task without an outbox row does not send or enqueue email, and records a manual-review signal."""
        # Create match directly without outbox row
        m = Match.objects.create(
            candidate_profile=self.profile,
            job=self.job,
            match_score=92,
            match_reason="Legacy match created without outbox",
            status=Match.Status.SUGGESTED,
            recruiter_notified_at=None,
        )
        self.assertEqual(NotificationOutbox.objects.filter(match=m).count(), 0)

        # Execute legacy task
        res = notify_recruiter_high_match_task(str(m.id))

        self.assertFalse(res["delivered"])
        self.assertEqual(res["status"], "manual_review_required")
        self.assertIn("delivery status unknown", res["reason"])

        # Outbox row was created in PERMANENTLY_FAILED state (will not be dispatched by worker)
        outbox_records = NotificationOutbox.objects.filter(match=m)
        self.assertEqual(outbox_records.count(), 1)
        outbox = outbox_records.first()
        self.assertEqual(outbox.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertIsNone(outbox.provider_message_id)
        self.assertIsNone(outbox.delivered_at)
        self.assertEqual(outbox.retry_count, 0)
        self.assertEqual(outbox.max_retries, 0)
        self.assertTrue(outbox.payload.get("manual_review_required"))

        # Zero emails dispatched via send_mail
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_and_verification_emails_remain_functional(self):
        """Unrelated authentication emails continue to function normally with Django test mail backend."""
        res_reset = send_password_reset_email(
            to_email="test_user@example.com",
            uidb64="uid_test_123",
            token="token_test_abc",
        )
        self.assertTrue(res_reset)

        res_verify = send_verification_email(
            to_email="test_user@example.com",
            uidb64="uid_test_123",
            token="token_test_abc",
        )
        self.assertTrue(res_verify)

        # Both emails were dispatched to test outbox
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("Reset Your Password", mail.outbox[0].subject)
        self.assertIn("Verify Your Email", mail.outbox[1].subject)

    def test_no_live_http_or_smtp_connections(self):
        """Verifies zero live socket connections occur during legacy task execution."""
        m = Match.objects.create(
            candidate_profile=self.profile,
            job=self.job,
            match_score=94,
            status=Match.Status.SUGGESTED,
        )

        with patch.object(socket.socket, "connect", side_effect=RuntimeError("Live network call forbidden")):
            # Running legacy task completes without attempting any socket connection
            res = notify_recruiter_high_match_task(str(m.id))
            self.assertFalse(res["delivered"])
            self.assertEqual(res["status"], "manual_review_required")

            # Defused helper also completes with zero network connection
            res_defused = send_recruiter_high_match_notification(str(m.id))
            self.assertFalse(res_defused["delivered"])
