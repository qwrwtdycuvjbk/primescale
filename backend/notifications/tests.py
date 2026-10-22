"""
Unit tests for backend/notifications/client.py (ResendHTTPClient).

All tests strictly mock HTTP calls using unittest.mock.
Confirms zero real network calls occur.
"""

from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from notifications.client import (
    ResendClientError,
    ResendConfigurationError,
    ResendHTTPClient,
    ResendPermanentError,
    ResendResponse,
    ResendResponseError,
    ResendRetryableError,
    ResendValidationError,
    sanitize_error_message,
)


class ResendSanitizationTests(SimpleTestCase):
    """Verify secrets and bearer tokens are properly stripped from error strings."""

    def test_sanitize_error_message_strips_api_keys_and_bearer_tokens(self):
        raw = "Error sending request with Bearer re_1234567890abcdef and re_9876543210zyxwvu"
        sanitized = sanitize_error_message(raw)
        self.assertNotIn("re_1234567890abcdef", sanitized)
        self.assertNotIn("re_9876543210zyxwvu", sanitized)
        self.assertIn("[REDACTED_API_KEY]", sanitized)
        self.assertIn("Bearer [REDACTED_TOKEN]", sanitized)

    def test_sanitize_error_message_handles_empty(self):
        self.assertEqual(sanitize_error_message(""), "")
        self.assertEqual(sanitize_error_message(None), "")


@override_settings(
    RESEND_API_KEY="re_test_dummy_key_12345",
    RESEND_FROM_EMAIL="People Remotely <onboarding@resend.dev>",
    RESEND_API_URL="https://api.resend.com/emails",
    RESEND_CONNECT_TIMEOUT=2.5,
    RESEND_READ_TIMEOUT=8.5,
)
class ResendHTTPClientTests(SimpleTestCase):
    """Test suite for ResendHTTPClient mocking all outbound requests."""

    def setUp(self):
        super().setUp()
        self.mock_session = MagicMock(spec=requests.Session)
        self.client = ResendHTTPClient(
            api_key="re_test_dummy_key_12345",
            from_email="People Remotely <onboarding@resend.dev>",
            session=self.mock_session,
        )

    def _create_mock_response(self, status_code: int, json_data: dict | list | None = None, text: str = ""):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = status_code
        mock_resp.reason = f"Status {status_code}"
        if json_data is not None:
            mock_resp.json.return_value = json_data
            mock_resp.text = str(json_data)
        else:
            mock_resp.json.side_effect = ValueError("No JSON object could be decoded")
            mock_resp.text = text
        return mock_resp

    def test_successful_provider_response_200(self):
        """Test provider acceptance on HTTP 200 with id."""
        self.mock_session.post.return_value = self._create_mock_response(
            200, json_data={"id": "re_msg_successful_123"}
        )

        result = self.client.send_email(
            to="remote@people-prime.com",
            subject="High Match Alert",
            html="<p>Test</p>",
            idempotency_key="match:101:high_match_alert",
        )

        self.assertIsInstance(result, ResendResponse)
        self.assertEqual(result.message_id, "re_msg_successful_123")
        self.assertEqual(result.status_code, 200)

        # Verify call arguments
        self.mock_session.post.assert_called_once()
        _, kwargs = self.mock_session.post.call_args
        self.assertEqual(kwargs["json"]["to"], ["remote@people-prime.com"])
        self.assertEqual(kwargs["json"]["subject"], "High Match Alert")
        self.assertEqual(kwargs["json"]["html"], "<p>Test</p>")
        self.assertEqual(kwargs["json"]["from"], "People Remotely <onboarding@resend.dev>")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test_dummy_key_12345")
        self.assertEqual(kwargs["headers"]["Idempotency-Key"], "match:101:high_match_alert")
        self.assertEqual(kwargs["timeout"], (2.5, 8.5))

    def test_successful_provider_response_201(self):
        """Test provider acceptance on HTTP 201 Created."""
        self.mock_session.post.return_value = self._create_mock_response(
            201, json_data={"id": "re_msg_created_456"}
        )

        result = self.client.send_email(
            to=["remote@people-prime.com", "ops@peopleremotely.com"],
            subject="Candidate Interested",
            text="Candidate text only body",
        )

        self.assertEqual(result.message_id, "re_msg_created_456")
        self.assertEqual(result.status_code, 201)

        _, kwargs = self.mock_session.post.call_args
        self.assertEqual(kwargs["json"]["to"], ["remote@people-prime.com", "ops@peopleremotely.com"])
        self.assertNotIn("Idempotency-Key", kwargs["headers"])

    def test_idempotency_key_propagation(self):
        """Verify deterministic idempotency key is passed in headers."""
        self.mock_session.post.return_value = self._create_mock_response(
            200, json_data={"id": "re_idem_999"}
        )

        self.client.send_email(
            to="remote@people-prime.com",
            subject="Idempotency Test",
            text="Hello",
            idempotency_key="unique-test-key-abc-123",
        )

        _, kwargs = self.mock_session.post.call_args
        self.assertEqual(kwargs["headers"].get("Idempotency-Key"), "unique-test-key-abc-123")

    def test_missing_credentials_raises_configuration_error(self):
        """Verify missing API key raises ResendConfigurationError without network call."""
        client_no_key = ResendHTTPClient(api_key="", session=self.mock_session)
        with override_settings(RESEND_API_KEY=""):
            with self.assertRaises(ResendConfigurationError) as cm:
                client_no_key.send_email(
                    to="remote@people-prime.com",
                    subject="Test",
                    text="Hello",
                )
            self.assertIn("API key is not configured", str(cm.exception))
            self.mock_session.post.assert_not_called()

    def test_missing_sender_address_raises_configuration_error(self):
        """Verify missing sender email raises ResendConfigurationError without network call."""
        client_no_sender = ResendHTTPClient(
            api_key="re_some_key_12345",
            from_email="",
            session=self.mock_session,
        )
        with override_settings(RESEND_FROM_EMAIL=""):
            with self.assertRaises(ResendConfigurationError) as cm:
                client_no_sender.send_email(
                    to="remote@people-prime.com",
                    subject="Test",
                    text="Hello",
                )
            self.assertIn("sender email is not configured", str(cm.exception))
            self.mock_session.post.assert_not_called()

    def test_validation_errors(self):
        """Verify validation errors for recipient, subject, and body."""
        # Empty recipient
        with self.assertRaises(ResendValidationError):
            self.client.send_email(to=[], subject="Test", text="Hello")

        # Invalid recipient type
        with self.assertRaises(ResendValidationError):
            self.client.send_email(to=12345, subject="Test", text="Hello")

        # Empty subject
        with self.assertRaises(ResendValidationError):
            self.client.send_email(to="remote@people-prime.com", subject="   ", text="Hello")

        # Empty body (neither html nor text)
        with self.assertRaises(ResendValidationError):
            self.client.send_email(to="remote@people-prime.com", subject="Test", html=None, text=None)

        self.mock_session.post.assert_not_called()

    def test_connect_timeout_raises_retryable_error(self):
        """Verify requests.exceptions.ConnectTimeout translates to ResendRetryableError."""
        self.mock_session.post.side_effect = requests.exceptions.ConnectTimeout("Connect timed out")

        with self.assertRaises(ResendRetryableError) as cm:
            self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

        self.assertIn("timed out", str(cm.exception))

    def test_read_timeout_raises_retryable_error(self):
        """Verify requests.exceptions.ReadTimeout translates to ResendRetryableError."""
        self.mock_session.post.side_effect = requests.exceptions.ReadTimeout("Read timed out")

        with self.assertRaises(ResendRetryableError) as cm:
            self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

        self.assertIn("timed out", str(cm.exception))

    def test_connection_error_raises_retryable_error(self):
        """Verify network connection failures translate to ResendRetryableError."""
        self.mock_session.post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with self.assertRaises(ResendRetryableError) as cm:
            self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

        self.assertIn("connection failed", str(cm.exception))

    def test_rate_limit_429_raises_retryable_error(self):
        """Verify HTTP 429 raises ResendRetryableError."""
        self.mock_session.post.return_value = self._create_mock_response(
            429,
            json_data={"statusCode": 429, "message": "Too many requests", "name": "rate_limit_exceeded"},
        )

        with self.assertRaises(ResendRetryableError) as cm:
            self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

        self.assertIn("429", str(cm.exception))
        self.assertIn("Too many requests", str(cm.exception))

    def test_server_errors_raise_retryable_error(self):
        """Verify HTTP 500, 502, 503, 504 raise ResendRetryableError."""
        for code in [500, 502, 503, 504]:
            self.mock_session.post.return_value = self._create_mock_response(
                code,
                json_data={"statusCode": code, "message": f"Server issue {code}"},
            )

            with self.assertRaises(ResendRetryableError) as cm:
                self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

            self.assertIn(str(code), str(cm.exception))

    def test_client_errors_raise_permanent_error(self):
        """Verify HTTP 400, 401, 403, 422 raise ResendPermanentError."""
        test_cases = [
            (400, "Bad Request"),
            (401, "API key is invalid"),
            (403, "Forbidden domain"),
            (422, "The to field is required"),
        ]
        for code, msg in test_cases:
            self.mock_session.post.return_value = self._create_mock_response(
                code,
                json_data={"statusCode": code, "message": msg},
            )

            with self.assertRaises(ResendPermanentError) as cm:
                self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

            self.assertIn(str(code), str(cm.exception))
            self.assertIn(msg, str(cm.exception))

    def test_malformed_json_response_raises_response_error(self):
        """Verify HTTP 200 with invalid JSON raises ResendResponseError."""
        self.mock_session.post.return_value = self._create_mock_response(
            200, json_data=None, text="<html>502 Bad Gateway</html>"
        )

        with self.assertRaises(ResendResponseError) as cm:
            self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

        self.assertIn("malformed", str(cm.exception).lower())

    def test_missing_id_in_response_raises_response_error(self):
        """Verify HTTP 200 without 'id' raises ResendResponseError."""
        self.mock_session.post.return_value = self._create_mock_response(
            200, json_data={"status": "sent"}  # Missing 'id'
        )

        with self.assertRaises(ResendResponseError) as cm:
            self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

        self.assertIn("without a valid 'id'", str(cm.exception))

    def test_non_dict_json_in_response_raises_response_error(self):
        """Verify HTTP 200 with JSON list raises ResendResponseError."""
        self.mock_session.post.return_value = self._create_mock_response(
            200, json_data=["re_123"]
        )

        with self.assertRaises(ResendResponseError) as cm:
            self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

        self.assertIn("unexpected non-dict JSON body", str(cm.exception))

    def test_error_message_sanitizes_credentials(self):
        """Verify error message sanitizes sensitive tokens returned in provider response."""
        self.mock_session.post.return_value = self._create_mock_response(
            401,
            json_data={
                "statusCode": 401,
                "message": "Key re_super_secret_token_123456789 was rejected with Bearer invalid_jwt_abc123.",
            },
        )

        with self.assertRaises(ResendPermanentError) as cm:
            self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")

        err_msg = str(cm.exception)
        self.assertNotIn("re_super_secret_token_123456789", err_msg)
        self.assertNotIn("invalid_jwt_abc123", err_msg)
        self.assertIn("[REDACTED_API_KEY]", err_msg)
        self.assertIn("Bearer [REDACTED_TOKEN]", err_msg)

    def test_default_settings_resolution(self):
        """Verify client resolves configuration from Django settings if arguments omitted."""
        default_client = ResendHTTPClient()
        self.assertEqual(default_client._get_api_key(), "re_test_dummy_key_12345")
        self.assertEqual(default_client.from_email, "People Remotely <onboarding@resend.dev>")
        self.assertEqual(default_client.api_url, "https://api.resend.com/emails")
        self.assertEqual(default_client.connect_timeout, 2.5)
        self.assertEqual(default_client.read_timeout, 8.5)

    def test_no_real_network_calls_occur(self):
        """Ensure socket level connection is never attempted when mock session is used."""
        import socket
        with patch.object(socket.socket, "connect", side_effect=RuntimeError("Real network call forbidden")):
            self.mock_session.post.return_value = self._create_mock_response(
                200, json_data={"id": "re_verified_no_network"}
            )
            res = self.client.send_email(to="remote@people-prime.com", subject="Test", text="Body")
            self.assertEqual(res.message_id, "re_verified_no_network")

    def test_provider_idempotency_limitations_documented(self):
        """Verify client module and class document idempotency guarantees and limitations."""
        import notifications.client as client_module

        module_doc = client_module.__doc__ or ""
        self.assertIn("Idempotency Key Semantics", module_doc)
        self.assertIn("24 hours", module_doc)
        self.assertIn("Ambiguous Timeouts and Recovery", module_doc)
        self.assertIn("Downstream Delivery Realities", module_doc)
        self.assertIn("ACCEPTED_BY_PROVIDER", module_doc)