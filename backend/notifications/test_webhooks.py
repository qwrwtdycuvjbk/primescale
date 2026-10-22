"""
Tests for Resend Webhook Verification and Outbox Ingestion.

Covers:
1. Valid signature and supported delivery event.
2. Missing signing secret, invalid signature, tampered body, expired timestamp.
3. Malformed payload, non-dict JSON, missing fields, unsupported events.
4. Duplicate event delivery (idempotency).
5. Fast-delivery correlation race handling (409 Conflict for fresh unmatched, 200 after retry, safe acknowledge for stale unmatched).
6. Request body size boundaries (65536 byte limit: 413 for oversized, 200 for exact boundary).
7. Out-of-order and repeated events.
8. Hardened bounce handling (null, string, list, missing bounce data).
9. Complaint handling.
10. Concurrent updates and terminal-state protection.
11. Verification that no email dispatch or external network access occurs.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from candidates.models import CandidateProfile
from companies.models import Company
from jobs.models import Job
from matching.models import Match
from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType
from notifications.webhooks import (
    EVENT_EMAIL_BOUNCED,
    EVENT_EMAIL_COMPLAINED,
    EVENT_EMAIL_DELIVERED,
    EVENT_EMAIL_DELIVERY_DELAYED,
    EVENT_EMAIL_SENT,
    WebhookExpiredError,
    WebhookInvalidSignatureError,
    WebhookMissingHeadersError,
    WebhookSecretNotConfiguredError,
    WebhookUnmatchedMessageRetryableError,
    WebhookVerificationError,
    handle_resend_webhook_event,
    verify_resend_webhook,
)

User = get_user_model()

TEST_SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"


def generate_svix_headers(raw_body: bytes, secret: str = TEST_SECRET, svix_id: str = None, timestamp: int = None):
    """Utility to generate valid Svix headers for testing."""
    svix_id = svix_id or f"msg_{uuid.uuid4().hex}"
    timestamp = timestamp if timestamp is not None else int(time.time())
    secret_part = secret[len("whsec_"):] if secret.startswith("whsec_") else secret
    secret_bytes = base64.b64decode(secret_part)
    signed_payload = f"{svix_id}.{timestamp}.".encode("utf-8") + raw_body
    digest = hmac.new(secret_bytes, signed_payload, hashlib.sha256).digest()
    sig_b64 = base64.b64encode(digest).decode("utf-8")
    return {
        "HTTP_SVIX_ID": svix_id,
        "HTTP_SVIX_TIMESTAMP": str(timestamp),
        "HTTP_SVIX_SIGNATURE": f"v1,{sig_b64}",
    }, svix_id, timestamp


class WebhookSignatureVerificationUnitTests(TestCase):
    """Unit tests for verify_resend_webhook cryptographic validation."""

    def test_valid_signature_succeeds(self):
        raw_body = b'{"type": "email.delivered"}'
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)
        result = verify_resend_webhook(raw_body, headers, secret=TEST_SECRET, tolerance=300)
        self.assertTrue(result)

    def test_multiple_signatures_in_header_succeeds(self):
        raw_body = b'{"type": "email.delivered"}'
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)
        headers["HTTP_SVIX_SIGNATURE"] = f"v1,invalidsig12345 {headers['HTTP_SVIX_SIGNATURE']}"
        result = verify_resend_webhook(raw_body, headers, secret=TEST_SECRET, tolerance=300)
        self.assertTrue(result)

    def test_missing_secret_raises_error(self):
        raw_body = b'{"type": "email.delivered"}'
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)
        with self.assertRaises(WebhookSecretNotConfiguredError):
            verify_resend_webhook(raw_body, headers, secret="", tolerance=300)

    def test_missing_headers_raises_error(self):
        raw_body = b'{"type": "email.delivered"}'
        with self.assertRaises(WebhookMissingHeadersError):
            verify_resend_webhook(raw_body, {}, secret=TEST_SECRET, tolerance=300)

        with self.assertRaises(WebhookMissingHeadersError):
            verify_resend_webhook(raw_body, {"HTTP_SVIX_ID": "123", "HTTP_SVIX_TIMESTAMP": "123"}, secret=TEST_SECRET)

    def test_expired_timestamp_raises_error(self):
        raw_body = b'{"type": "email.delivered"}'
        expired_ts = int(time.time()) - 400
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET, timestamp=expired_ts)
        with self.assertRaises(WebhookExpiredError):
            verify_resend_webhook(raw_body, headers, secret=TEST_SECRET, tolerance=300)

    def test_future_timestamp_outside_tolerance_raises_error(self):
        raw_body = b'{"type": "email.delivered"}'
        future_ts = int(time.time()) + 400
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET, timestamp=future_ts)
        with self.assertRaises(WebhookExpiredError):
            verify_resend_webhook(raw_body, headers, secret=TEST_SECRET, tolerance=300)

    def test_tampered_signature_raises_error(self):
        raw_body = b'{"type": "email.delivered"}'
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)
        headers["HTTP_SVIX_SIGNATURE"] = "v1,tampered_signature_base64_string="
        with self.assertRaises(WebhookInvalidSignatureError):
            verify_resend_webhook(raw_body, headers, secret=TEST_SECRET, tolerance=300)

    def test_tampered_body_raises_error(self):
        raw_body = b'{"type": "email.delivered"}'
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)
        tampered_body = b'{"type": "email.delivered", "tampered": true}'
        with self.assertRaises(WebhookInvalidSignatureError):
            verify_resend_webhook(tampered_body, headers, secret=TEST_SECRET, tolerance=300)

    def test_malformed_timestamp_raises_error(self):
        raw_body = b'{"type": "email.delivered"}'
        headers = {
            "HTTP_SVIX_ID": "msg_123",
            "HTTP_SVIX_TIMESTAMP": "not_an_int",
            "HTTP_SVIX_SIGNATURE": "v1,abc",
        }
        with self.assertRaises(WebhookVerificationError):
            verify_resend_webhook(raw_body, headers, secret=TEST_SECRET, tolerance=300)


@override_settings(RESEND_WEBHOOK_SECRET=TEST_SECRET)
class ResendWebhookEndpointIntegrationTests(TestCase):
    """
    End-to-end HTTP integration tests for the /api/v1/notifications/webhooks/resend/ endpoint.
    """

    def setUp(self):
        super().setUp()
        self.webhook_url = reverse("v1:notifications:resend-webhook")

        self.employer_user = User.objects.create_user(
            email="emp_wh@example.com", password="Password123!", role=User.Role.EMPLOYER
        )
        self.candidate_user = User.objects.create_user(
            email="cand_wh@example.com", password="Password123!", role=User.Role.CANDIDATE
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Senior Architect",
            current_title="Senior Architect",
            years_experience=8,
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Apex Scale Corp",
            description="Cloud platforms",
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Principal Infrastructure Lead",
            description="Scalable Kubernetes systems",
            role_type="full-time",
            experience_level="senior",
            status=Job.Status.ACTIVE,
        )
        self.match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=94,
            status=Match.Status.MUTUAL_FIT,
        )

        self.message_id = f"re_{uuid.uuid4().hex[:16]}"
        self.outbox_record = NotificationOutbox.objects.create(
            match=self.match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
            idempotency_key=f"match:{self.match.id}:high_match_alert",
            status=DeliveryStatus.ACCEPTED_BY_PROVIDER,
            recipient_email="remote@people-prime.com",
            subject="High Match Alert",
            payload={"match_id": str(self.match.id)},
            provider_message_id=self.message_id,
        )

    # -----------------------------------------------------------------------
    # Step 5.1 — Valid signature and supported delivery event
    # -----------------------------------------------------------------------
    def test_valid_signature_and_delivery_event_transitions_to_confirmed_delivered(self):
        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "created_at": "2026-10-16T10:00:00.000Z",
            "data": {
                "email_id": self.message_id,
                "from": "updates@primescale.io",
                "to": ["remote@people-prime.com"],
                "subject": "High Match Alert",
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertEqual(response.json()["result"]["status"], "confirmed_delivered")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.CONFIRMED_DELIVERED)
        self.assertIsNotNone(self.outbox_record.delivered_at)
        self.assertIsNone(self.outbox_record.last_error)
        self.assertIn(svix_id, self.outbox_record.payload.get("webhook_events", {}))

    # -----------------------------------------------------------------------
    # Step 5.2 — Missing signing secret and invalid signature
    # -----------------------------------------------------------------------
    @override_settings(RESEND_WEBHOOK_SECRET="")
    def test_missing_signing_secret_returns_503(self):
        payload_dict = {"type": EVENT_EMAIL_DELIVERED, "data": {"email_id": self.message_id}}
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["error"])

    def test_invalid_signature_returns_400(self):
        payload_dict = {"type": EVENT_EMAIL_DELIVERED, "data": {"email_id": self.message_id}}
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)
        headers["HTTP_SVIX_SIGNATURE"] = "v1,invalidsignaturestring="

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_svix_headers_returns_400(self):
        payload_dict = {"type": EVENT_EMAIL_DELIVERED, "data": {"email_id": self.message_id}}
        raw_body = json.dumps(payload_dict).encode("utf-8")

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_expired_timestamp_returns_400(self):
        payload_dict = {"type": EVENT_EMAIL_DELIVERED, "data": {"email_id": self.message_id}}
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET, timestamp=int(time.time()) - 500)

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 400)

    # -----------------------------------------------------------------------
    # Step 5.3 — Malformed payload and unsupported event
    # -----------------------------------------------------------------------
    def test_malformed_json_returns_400(self):
        raw_body = b'{"type": "email.delivered", "broken_json": '
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Malformed JSON", response.json()["error"])

    def test_non_dict_json_returns_400(self):
        raw_body = b'["item1", "item2"]'
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_unsupported_event_returns_400(self):
        payload_dict = {
            "type": "domain.created",
            "data": {"email_id": self.message_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported event type", response.json()["error"])

    def test_missing_email_id_returns_400(self):
        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "data": {"no_email_id_here": True},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing or invalid 'email_id'", response.json()["error"])

    def test_unsupported_http_method_returns_405(self):
        response = self.client.get(self.webhook_url)
        self.assertEqual(response.status_code, 405)

        response = self.client.put(self.webhook_url, data={}, content_type="application/json")
        self.assertEqual(response.status_code, 405)

        response = self.client.delete(self.webhook_url)
        self.assertEqual(response.status_code, 405)

    def test_unsupported_content_type_returns_415(self):
        response = self.client.post(
            self.webhook_url,
            data="text payload",
            content_type="text/plain",
        )
        self.assertEqual(response.status_code, 415)

    # -----------------------------------------------------------------------
    # Step 5.4 — Request Body Size Limits (65,536 bytes)
    # -----------------------------------------------------------------------
    def test_oversized_request_body_rejected_with_413(self):
        # 65537 bytes (> 65536 max limit)
        oversized_data = {"type": EVENT_EMAIL_DELIVERED, "data": {"email_id": self.message_id}, "padding": "x" * 65500}
        raw_body = json.dumps(oversized_data).encode("utf-8")
        self.assertGreater(len(raw_body), 65536)

        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)
        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("Payload too large", response.json()["error"])

    def test_request_body_at_exact_size_boundary_accepted(self):
        # Build payload of exactly 65536 bytes
        base_dict = {"type": EVENT_EMAIL_DELIVERED, "data": {"email_id": self.message_id}, "pad": ""}
        base_bytes = json.dumps(base_dict).encode("utf-8")
        pad_needed = 65536 - len(base_bytes)
        base_dict["pad"] = "a" * pad_needed
        exact_body = json.dumps(base_dict).encode("utf-8")
        self.assertEqual(len(exact_body), 65536)

        headers, svix_id, ts = generate_svix_headers(exact_body, TEST_SECRET)
        response = self.client.post(
            self.webhook_url,
            data=exact_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["status"], "confirmed_delivered")

    # -----------------------------------------------------------------------
    # Step 5.5 — Fast-Delivery Correlation Race & Unknown Provider IDs
    # -----------------------------------------------------------------------
    def test_fresh_unmatched_event_returns_retryable_409_conflict(self):
        unknown_id = f"re_fresh_racing_{uuid.uuid4().hex[:12]}"
        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "data": {"email_id": unknown_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        # Fresh timestamp: current time (age 0s <= 60s window)
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET, timestamp=int(time.time()))

        response = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["provider_message_id"], unknown_id)
        self.assertIn("retry requested", response.json()["error"])

        # Confirm no records modified
        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.ACCEPTED_BY_PROVIDER)

    def test_retried_event_succeeds_after_worker_commits_provider_message_id(self):
        racing_message_id = f"re_race_resolved_{uuid.uuid4().hex[:12]}"
        racing_record = NotificationOutbox.objects.create(
            match=self.match,
            notification_type=NotificationType.CANDIDATE_INTERESTED,
            idempotency_key=f"match:{self.match.id}:candidate_interested",
            status=DeliveryStatus.PROCESSING,
            recipient_email="remote@people-prime.com",
            subject="Candidate Interested",
            payload={"match_id": str(self.match.id)},
            provider_message_id=None,  # Worker has not committed provider_message_id yet!
        )

        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "data": {"email_id": racing_message_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET, timestamp=int(time.time()))

        # Attempt 1: Webhook arrives before worker commits -> 409 Conflict (signals Resend to retry)
        res1 = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res1.status_code, 409)

        # Worker completes: commits provider_message_id and transitions to ACCEPTED_BY_PROVIDER
        racing_record.provider_message_id = racing_message_id
        racing_record.status = DeliveryStatus.ACCEPTED_BY_PROVIDER
        racing_record.save()

        # Attempt 2: Resend retries with the same svix_id and payload -> succeeds!
        res2 = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["result"]["status"], "confirmed_delivered")

        racing_record.refresh_from_db()
        self.assertEqual(racing_record.status, DeliveryStatus.CONFIRMED_DELIVERED)
        self.assertIsNotNone(racing_record.delivered_at)

    def test_stale_unmatched_event_acknowledged_safely_without_retry(self):
        unknown_id = f"re_stale_{uuid.uuid4().hex[:12]}"
        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "data": {"email_id": unknown_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        # Stale timestamp: 120s ago (age 120s > 60s retry window, but <= 300s replay tolerance)
        stale_ts = int(time.time()) - 120
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET, timestamp=stale_ts)

        response = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["status"], "ignored")
        self.assertEqual(response.json()["result"]["reason"], "unmatched_after_retry_window")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.ACCEPTED_BY_PROVIDER)

    # -----------------------------------------------------------------------
    # Step 5.6 — Duplicate event delivery
    # -----------------------------------------------------------------------
    def test_duplicate_event_delivery_is_idempotent(self):
        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "created_at": "2026-10-16T10:00:00.000Z",
            "data": {"email_id": self.message_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res1 = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["result"]["status"], "confirmed_delivered")

        self.outbox_record.refresh_from_db()
        first_delivered_at = self.outbox_record.delivered_at

        # Second delivery with exact same svix_id
        res2 = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["result"]["status"], "duplicate")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.CONFIRMED_DELIVERED)
        self.assertEqual(self.outbox_record.delivered_at, first_delivered_at)

    # -----------------------------------------------------------------------
    # Step 5.7 — Out-of-order and repeated events
    # -----------------------------------------------------------------------
    def test_out_of_order_sent_event_does_not_downgrade_confirmed_delivered(self):
        self.outbox_record.status = DeliveryStatus.CONFIRMED_DELIVERED
        self.outbox_record.delivered_at = timezone.now()
        self.outbox_record.save()

        payload_dict = {
            "type": EVENT_EMAIL_SENT,
            "data": {"email_id": self.message_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.CONFIRMED_DELIVERED)
        self.assertIn("sent_event", self.outbox_record.payload)

    def test_out_of_order_bounce_does_not_overwrite_valid_delivery_evidence(self):
        delivered_timestamp = timezone.now()
        self.outbox_record.status = DeliveryStatus.CONFIRMED_DELIVERED
        self.outbox_record.delivered_at = delivered_timestamp
        self.outbox_record.save()

        payload_dict = {
            "type": EVENT_EMAIL_BOUNCED,
            "data": {
                "email_id": self.message_id,
                "bounce": {"type": "Transient", "message": "Late bounce notice"},
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "stale_bounce_ignored")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.CONFIRMED_DELIVERED)
        self.assertEqual(self.outbox_record.delivered_at, delivered_timestamp)
        self.assertIn("stale_bounce", self.outbox_record.payload)

    def test_sent_event_never_treats_provider_acceptance_as_delivery(self):
        payload_dict = {
            "type": EVENT_EMAIL_SENT,
            "data": {"email_id": self.message_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.ACCEPTED_BY_PROVIDER)
        self.assertIsNone(self.outbox_record.delivered_at)

    # -----------------------------------------------------------------------
    # Step 5.8 — Hardened Bounce Handling (Null, Strings, Lists, Missing)
    # -----------------------------------------------------------------------
    def test_bounce_event_with_valid_dict_marks_permanently_failed(self):
        payload_dict = {
            "type": EVENT_EMAIL_BOUNCED,
            "data": {
                "email_id": self.message_id,
                "bounce": {
                    "type": "Permanent",
                    "subType": "Suppressed",
                    "message": "Recipient address is on the suppression list",
                },
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "marked_permanently_failed")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertIsNone(self.outbox_record.delivered_at)
        self.assertIn("Recipient address is on the suppression list", self.outbox_record.last_error)
        self.assertEqual(self.outbox_record.payload["bounce"]["subType"], "Suppressed")

    def test_bounce_event_with_null_bounce_data_handled_gracefully(self):
        payload_dict = {
            "type": EVENT_EMAIL_BOUNCED,
            "data": {
                "email_id": self.message_id,
                "bounce": None,
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "marked_permanently_failed")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertIn("Email rejected by recipient mail server", self.outbox_record.last_error)

    def test_bounce_event_with_string_diagnostic_handled_gracefully(self):
        payload_dict = {
            "type": EVENT_EMAIL_BOUNCED,
            "data": {
                "email_id": self.message_id,
                "bounce": "550 5.1.1 User unknown",
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "marked_permanently_failed")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertIn("550 5.1.1 User unknown", self.outbox_record.last_error)

    def test_bounce_event_with_list_diagnostic_handled_gracefully(self):
        payload_dict = {
            "type": EVENT_EMAIL_BOUNCED,
            "data": {
                "email_id": self.message_id,
                "bounce": ["Diagnostic line 1", "Diagnostic line 2"],
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "marked_permanently_failed")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.PERMANENTLY_FAILED)

    def test_bounce_event_missing_bounce_key_handled_gracefully(self):
        payload_dict = {
            "type": EVENT_EMAIL_BOUNCED,
            "data": {
                "email_id": self.message_id,
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "marked_permanently_failed")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.PERMANENTLY_FAILED)

    # -----------------------------------------------------------------------
    # Step 5.9 — Complaint and Delay Handling
    # -----------------------------------------------------------------------
    def test_complaint_event_records_metadata_without_reverting_delivery(self):
        self.outbox_record.status = DeliveryStatus.CONFIRMED_DELIVERED
        self.outbox_record.delivered_at = timezone.now()
        self.outbox_record.save()

        payload_dict = {
            "type": EVENT_EMAIL_COMPLAINED,
            "data": {
                "email_id": self.message_id,
                "to": ["remote@people-prime.com"],
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "complaint_recorded")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.CONFIRMED_DELIVERED)
        self.assertIn("complaint", self.outbox_record.payload)

    def test_delivery_delayed_records_notice_without_modifying_status(self):
        payload_dict = {
            "type": EVENT_EMAIL_DELIVERY_DELAYED,
            "data": {
                "email_id": self.message_id,
                "delay_reason": "Mailbox server rate limited",
            },
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "delay_recorded")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.ACCEPTED_BY_PROVIDER)
        self.assertIn("delivery_delayed", self.outbox_record.payload)

    # -----------------------------------------------------------------------
    # Step 5.10 — Terminal-State Protection
    # -----------------------------------------------------------------------
    def test_cancelled_record_never_reactivated_by_webhook(self):
        self.outbox_record.status = DeliveryStatus.CANCELLED
        self.outbox_record.last_error = "Cancelled due to candidate ineligibility"
        self.outbox_record.save()

        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "data": {"email_id": self.message_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "terminal_state_protected")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.CANCELLED)
        self.assertIsNone(self.outbox_record.delivered_at)
        self.assertIn(svix_id, self.outbox_record.payload["webhook_events"])

    def test_permanently_failed_record_never_reactivated_by_delivery_webhook(self):
        self.outbox_record.status = DeliveryStatus.PERMANENTLY_FAILED
        self.outbox_record.last_error = "Dismissed during manual triage"
        self.outbox_record.save()

        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "data": {"email_id": self.message_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"]["status"], "terminal_state_protected")

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.PERMANENTLY_FAILED)
        self.assertIsNone(self.outbox_record.delivered_at)

    def test_processing_record_safely_transitions_to_confirmed_delivered(self):
        self.outbox_record.status = DeliveryStatus.PROCESSING
        self.outbox_record.lease_token = uuid.uuid4()
        self.outbox_record.locked_at = timezone.now()
        self.outbox_record.locked_by = "worker_1"
        self.outbox_record.save()

        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "data": {"email_id": self.message_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        res = self.client.post(self.webhook_url, data=raw_body, content_type="application/json", **headers)
        self.assertEqual(res.status_code, 200)

        self.outbox_record.refresh_from_db()
        self.assertEqual(self.outbox_record.status, DeliveryStatus.CONFIRMED_DELIVERED)
        self.assertIsNone(self.outbox_record.lease_token)
        self.assertIsNone(self.outbox_record.locked_at)

    # -----------------------------------------------------------------------
    # Step 5.11 — No email dispatch or external network access
    # -----------------------------------------------------------------------
    @patch("notifications.client.ResendHTTPClient.send_email")
    def test_webhook_ingestion_never_calls_resend_send_email(self, mock_send_email):
        payload_dict = {
            "type": EVENT_EMAIL_DELIVERED,
            "data": {"email_id": self.message_id},
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        headers, svix_id, ts = generate_svix_headers(raw_body, TEST_SECRET)

        response = self.client.post(
            self.webhook_url,
            data=raw_body,
            content_type="application/json",
            **headers,
        )
        self.assertEqual(response.status_code, 200)
        mock_send_email.assert_not_called()
