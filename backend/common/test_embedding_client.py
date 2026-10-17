"""
Unit tests for the NVIDIA NIM Embedding Client (backend/common/embedding_client.py).

All HTTP requests are mocked deterministically.
No live external API calls are made.
"""

import json
import math
from unittest.mock import MagicMock, call, patch

import requests
from django.test import SimpleTestCase, override_settings

from common.embedding_client import (
    DEFAULT_NVIDIA_API_URL,
    MAX_INPUT_CHARACTERS,
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    EmbeddingAuthenticationError,
    EmbeddingClientError,
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    EmbeddingPermanentError,
    EmbeddingRateLimitError,
    EmbeddingResponseError,
    EmbeddingResult,
    EmbeddingTransientError,
    EmbeddingValidationError,
    NvidiaEmbeddingClient,
)


def make_mock_embedding_vector(dim: int = TARGET_EMBEDDING_DIMENSIONS, val: float = 0.05) -> list[float]:
    """Helper to generate a mock vector of specified dimension."""
    return [val] * dim


def make_mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text_data: str | None = None,
    headers: dict | None = None,
) -> requests.Response:
    """Helper to construct a mock requests.Response object."""
    resp = requests.Response()
    resp.status_code = status_code
    resp.headers = requests.structures.CaseInsensitiveDict(headers or {})
    if json_data is not None:
        resp._content = json.dumps(json_data).encode("utf-8")
        resp.headers["Content-Type"] = "application/json"
    elif text_data is not None:
        resp._content = text_data.encode("utf-8")
    else:
        resp._content = b""
    return resp


class NvidiaEmbeddingClientTests(SimpleTestCase):
    """Deterministic test suite for NvidiaEmbeddingClient."""

    def setUp(self):
        super().setUp()
        self.dummy_api_key = "nvapi-test-dummy-key-for-unit-testing"
        self.client = NvidiaEmbeddingClient(
            api_key=self.dummy_api_key,
            max_retries=2,
            base_delay=0.01,
            max_delay=0.05,
            max_retry_after=5.0,
        )

    # ------------------------------------------------------------------------
    # 1. Passage Input Success
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_passage_input_success(self, mock_post):
        mock_vec = make_mock_embedding_vector(2048, 0.01)
        mock_post.return_value = make_mock_response(
            status_code=200,
            json_data={
                "data": [{"embedding": mock_vec, "index": 0}],
                "model": TARGET_EMBEDDING_MODEL,
                "usage": {"total_tokens": 42},
            },
        )

        sample_passage = "Senior Python Engineer with 10 years of Django experience."
        result = self.client.embed(sample_passage, input_type="passage")

        self.assertIsInstance(result, EmbeddingResult)
        self.assertEqual(result.dimensions, 2048)
        self.assertEqual(len(result.embedding), 2048)
        self.assertEqual(result.input_type, "passage")
        self.assertEqual(result.model, TARGET_EMBEDDING_MODEL)
        self.assertEqual(result.token_count, 42)

        # Verify request payload
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["input"], [sample_passage])
        self.assertEqual(payload["input_type"], "passage")
        self.assertEqual(payload["model"], TARGET_EMBEDDING_MODEL)
        self.assertEqual(payload["encoding_format"], "float")
        self.assertEqual(payload["truncate"], "NONE")

    # ------------------------------------------------------------------------
    # 2. Query Input Success
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_query_input_success(self, mock_post):
        mock_vec = make_mock_embedding_vector(2048, 0.02)
        mock_post.return_value = make_mock_response(
            status_code=200,
            json_data={
                "data": [{"embedding": mock_vec, "index": 0}],
                "model": TARGET_EMBEDDING_MODEL,
                "usage": {"total_tokens": 10},
            },
        )

        sample_query = "Remote Python PostgreSQL jobs"
        result = self.client.embed(sample_query, input_type="query")

        self.assertIsInstance(result, EmbeddingResult)
        self.assertEqual(result.dimensions, 2048)
        self.assertEqual(result.input_type, "query")

        # Verify request payload input_type
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["input_type"], "query")

    # ------------------------------------------------------------------------
    # 3. Authentication & Request Construction Without Leaking Credentials
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_authentication_and_request_construction_headers(self, mock_post):
        mock_vec = make_mock_embedding_vector(2048)
        mock_post.return_value = make_mock_response(
            status_code=200,
            json_data={"data": [{"embedding": mock_vec}]},
        )

        self.client.embed("Test text", input_type="passage")

        mock_post.assert_called_once()
        url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        self.assertEqual(url, "https://integrate.api.nvidia.com/v1/embeddings")
        self.assertEqual(DEFAULT_NVIDIA_API_URL, "https://integrate.api.nvidia.com/v1/embeddings")

        headers = kwargs["headers"]
        self.assertEqual(headers["Authorization"], f"Bearer {self.dummy_api_key}")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")

        # Ensure representation of client does not expose secret key
        client_repr = repr(self.client)
        self.assertNotIn(self.dummy_api_key, client_repr)

    # ------------------------------------------------------------------------
    # 4. Successful 2048-Dimensional Response Handling
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_successful_2048_dimensional_response(self, mock_post):
        vec = [i * 0.0001 for i in range(2048)]
        mock_post.return_value = make_mock_response(
            status_code=200,
            json_data={"data": [{"embedding": vec}]},
        )

        result = self.client.embed("Any valid text", input_type="passage")
        self.assertEqual(len(result.embedding), 2048)
        self.assertEqual(result.dimensions, 2048)
        self.assertAlmostEqual(result.embedding[10], 0.0010, places=6)

    # ------------------------------------------------------------------------
    # 5. Empty Input, Whitespace-only, and Invalid Input Type
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_empty_input_and_invalid_input_type(self, mock_post):
        # Empty string
        with self.assertRaises(EmbeddingValidationError) as ctx:
            self.client.embed("", input_type="passage")
        self.assertIn("cannot be empty or whitespace-only", str(ctx.exception))

        # Whitespace-only string
        with self.assertRaises(EmbeddingValidationError) as ctx:
            self.client.embed("   \t\n  ", input_type="passage")
        self.assertIn("cannot be empty or whitespace-only", str(ctx.exception))

        # Non-string input
        with self.assertRaises(EmbeddingValidationError) as ctx:
            self.client.embed(None, input_type="passage")  # type: ignore
        self.assertIn("must be a string", str(ctx.exception))

        # Invalid input type
        with self.assertRaises(EmbeddingValidationError) as ctx:
            self.client.embed("Valid text", input_type="document")  # type: ignore
        self.assertIn("Invalid input_type 'document'", str(ctx.exception))

        with self.assertRaises(EmbeddingValidationError) as ctx:
            self.client.embed("Valid text", input_type="")  # type: ignore
        self.assertIn("Invalid input_type ''", str(ctx.exception))

        # Exceeding maximum character limit
        too_long_text = "a" * (MAX_INPUT_CHARACTERS + 1)
        with self.assertRaises(EmbeddingValidationError) as ctx:
            self.client.embed(too_long_text, input_type="passage")
        self.assertIn("exceeds maximum supported limit", str(ctx.exception))

        # Verify no network calls were made
        mock_post.assert_not_called()

    # ------------------------------------------------------------------------
    # 6. Missing API Key Produces Configuration Error at Invocation
    # ------------------------------------------------------------------------
    @override_settings(NVIDIA_API_KEY="")
    @patch.object(requests.Session, "post")
    def test_missing_api_key(self, mock_post):
        # Instantiation without key must not raise at import/init time
        unconfigured_client = NvidiaEmbeddingClient(api_key="")

        # Invocation must raise EmbeddingConfigurationError
        with self.assertRaises(EmbeddingConfigurationError) as ctx:
            unconfigured_client.embed("Sample text", input_type="passage")

        self.assertIn("NVIDIA API key is not configured", str(ctx.exception))
        mock_post.assert_not_called()

    # ------------------------------------------------------------------------
    # 7. HTTP 401 and 403 Authentication Failures (No Retries)
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_http_401_unauthorized(self, mock_post):
        mock_post.return_value = make_mock_response(
            status_code=401,
            json_data={"detail": "Invalid API Key provided."},
        )

        with self.assertRaises(EmbeddingAuthenticationError) as ctx:
            self.client.embed("Sample text", input_type="passage")

        self.assertIn("authentication failed (401)", str(ctx.exception))
        self.assertIn("Verify that NVIDIA_API_KEY is valid", str(ctx.exception))
        # Ensure 401 is permanent and never retried
        self.assertEqual(mock_post.call_count, 1)

    @patch.object(requests.Session, "post")
    def test_http_403_forbidden(self, mock_post):
        mock_post.return_value = make_mock_response(
            status_code=403,
            json_data={"detail": "Account quota exhausted or access forbidden."},
        )

        with self.assertRaises(EmbeddingAuthenticationError) as ctx:
            self.client.embed("Sample text", input_type="passage")

        self.assertIn("authentication failed (403)", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 1)

    # ------------------------------------------------------------------------
    # 8. HTTP 429 and Retry-After Handling
    # ------------------------------------------------------------------------
    @patch("time.sleep")
    @patch.object(requests.Session, "post")
    def test_http_429_retry_after_success(self, mock_post, mock_sleep):
        mock_vec = make_mock_embedding_vector(2048)
        # Attempt 1: 429 with Retry-After: 0.1
        # Attempt 2: 200 OK
        mock_post.side_effect = [
            make_mock_response(status_code=429, headers={"Retry-After": "0.1"}),
            make_mock_response(status_code=200, json_data={"data": [{"embedding": mock_vec}]}),
        ]

        result = self.client.embed("Sample text", input_type="passage")
        self.assertEqual(result.dimensions, 2048)
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(0.1)

    @patch("time.sleep")
    @patch.object(requests.Session, "post")
    def test_http_429_retry_after_exceeds_maximum(self, mock_post, mock_sleep):
        # Retry-After is 60s, but client max_retry_after is 5.0s
        mock_post.return_value = make_mock_response(
            status_code=429, headers={"Retry-After": "60.0"}
        )

        with self.assertRaises(EmbeddingRateLimitError) as ctx:
            self.client.embed("Sample text", input_type="passage")

        self.assertIn("exceeds maximum allowed wait", str(ctx.exception))
        mock_sleep.assert_not_called()
        self.assertEqual(mock_post.call_count, 1)

    @patch("time.sleep")
    @patch.object(requests.Session, "post")
    def test_http_429_persistent_exhausts_retries(self, mock_post, mock_sleep):
        # 429 on all attempts (1 initial + 2 retries = 3 calls)
        mock_post.return_value = make_mock_response(status_code=429)

        with self.assertRaises(EmbeddingRateLimitError):
            self.client.embed("Sample text", input_type="passage")

        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    # ------------------------------------------------------------------------
    # 9. Transient Server Errors and Bounded Retry Behavior
    # ------------------------------------------------------------------------
    @patch("time.sleep")
    @patch.object(requests.Session, "post")
    def test_transient_503_recovers_on_retry(self, mock_post, mock_sleep):
        mock_vec = make_mock_embedding_vector(2048)
        # Attempt 1: 503 Service Unavailable
        # Attempt 2: 200 OK
        mock_post.side_effect = [
            make_mock_response(status_code=503, json_data={"detail": "Backend overloaded"}),
            make_mock_response(status_code=200, json_data={"data": [{"embedding": mock_vec}]}),
        ]

        result = self.client.embed("Sample text", input_type="passage")
        self.assertEqual(result.dimensions, 2048)
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    @patch.object(requests.Session, "post")
    def test_transient_500_persists_exhausts_retries(self, mock_post, mock_sleep):
        mock_post.return_value = make_mock_response(
            status_code=500, json_data={"detail": "Internal Server Error"}
        )

        with self.assertRaises(EmbeddingTransientError) as ctx:
            self.client.embed("Sample text", input_type="passage")

        self.assertIn("server error (500)", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 3)  # 1 initial + 2 retries
        self.assertEqual(mock_sleep.call_count, 2)

    @patch.object(requests.Session, "post")
    def test_non_transient_400_does_not_retry(self, mock_post):
        mock_post.return_value = make_mock_response(
            status_code=400, json_data={"detail": "Bad request format"}
        )

        with self.assertRaises(EmbeddingPermanentError) as ctx:
            self.client.embed("Sample text", input_type="passage")

        self.assertIn("client request error (400)", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 1)

    # ------------------------------------------------------------------------
    # 10. Timeout and Connection Errors
    # ------------------------------------------------------------------------
    @patch("time.sleep")
    @patch.object(requests.Session, "post")
    def test_timeout_and_connection_retries(self, mock_post, mock_sleep):
        mock_vec = make_mock_embedding_vector(2048)
        # Attempt 1: ConnectTimeout
        # Attempt 2: 200 OK
        mock_post.side_effect = [
            requests.exceptions.ConnectTimeout("Connection timed out"),
            make_mock_response(status_code=200, json_data={"data": [{"embedding": mock_vec}]}),
        ]

        result = self.client.embed("Sample text", input_type="passage")
        self.assertEqual(result.dimensions, 2048)
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    @patch.object(requests.Session, "post")
    def test_persistent_timeout_exhausts_retries(self, mock_post, mock_sleep):
        mock_post.side_effect = requests.exceptions.ReadTimeout("Read timed out")

        with self.assertRaises(EmbeddingTransientError) as ctx:
            self.client.embed("Sample text", input_type="passage")

        self.assertIn("Network/timeout error", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 3)

    # ------------------------------------------------------------------------
    # 11. Malformed JSON and Missing Response Fields
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_malformed_json_response(self, mock_post):
        mock_post.return_value = make_mock_response(
            status_code=200, text_data="<html>502 Bad Gateway</html>"
        )

        with self.assertRaises(EmbeddingResponseError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("malformed JSON", str(ctx.exception))

    @patch.object(requests.Session, "post")
    def test_missing_data_field(self, mock_post):
        mock_post.return_value = make_mock_response(
            status_code=200, json_data={"model": TARGET_EMBEDDING_MODEL}
        )

        with self.assertRaises(EmbeddingResponseError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("missing non-empty 'data' array", str(ctx.exception))

    @patch.object(requests.Session, "post")
    def test_empty_data_array(self, mock_post):
        mock_post.return_value = make_mock_response(
            status_code=200, json_data={"data": []}
        )

        with self.assertRaises(EmbeddingResponseError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("missing non-empty 'data' array", str(ctx.exception))

    @patch.object(requests.Session, "post")
    def test_missing_embedding_in_data_item(self, mock_post):
        mock_post.return_value = make_mock_response(
            status_code=200, json_data={"data": [{"index": 0}]}
        )

        with self.assertRaises(EmbeddingResponseError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("missing 'embedding' field", str(ctx.exception))

    # ------------------------------------------------------------------------
    # 12. Wrong Vector Dimension
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_dimension_mismatch_1536(self, mock_post):
        # 1536 dims instead of 2048
        wrong_vec = make_mock_embedding_vector(1536)
        mock_post.return_value = make_mock_response(
            status_code=200, json_data={"data": [{"embedding": wrong_vec}]}
        )

        with self.assertRaises(EmbeddingDimensionError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("Dimension mismatch: expected 2048 dimensions, received 1536", str(ctx.exception))

    @patch.object(requests.Session, "post")
    def test_dimension_mismatch_3(self, mock_post):
        wrong_vec = [0.1, 0.2, 0.3]
        mock_post.return_value = make_mock_response(
            status_code=200, json_data={"data": [{"embedding": wrong_vec}]}
        )

        with self.assertRaises(EmbeddingDimensionError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("Dimension mismatch: expected 2048 dimensions, received 3", str(ctx.exception))

    # ------------------------------------------------------------------------
    # 13. Non-Finite Values and Non-Numeric Values
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_non_finite_nan_value(self, mock_post):
        vec = make_mock_embedding_vector(2048)
        vec[100] = float("nan")
        mock_post.return_value = make_mock_response(
            status_code=200, json_data={"data": [{"embedding": vec}]}
        )

        with self.assertRaises(EmbeddingDimensionError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("non-finite numeric value (nan)", str(ctx.exception))

    @patch.object(requests.Session, "post")
    def test_non_finite_infinity_value(self, mock_post):
        vec = make_mock_embedding_vector(2048)
        vec[500] = float("inf")
        mock_post.return_value = make_mock_response(
            status_code=200, json_data={"data": [{"embedding": vec}]}
        )

        with self.assertRaises(EmbeddingDimensionError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("non-finite numeric value (inf)", str(ctx.exception))

    @patch.object(requests.Session, "post")
    def test_non_numeric_string_value(self, mock_post):
        vec = make_mock_embedding_vector(2048)
        vec[10] = "0.05"  # type: ignore
        mock_post.return_value = make_mock_response(
            status_code=200, json_data={"data": [{"embedding": vec}]}
        )

        with self.assertRaises(EmbeddingDimensionError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("non-numeric value of type str", str(ctx.exception))

    @patch.object(requests.Session, "post")
    def test_boolean_value_rejected(self, mock_post):
        vec = make_mock_embedding_vector(2048)
        vec[20] = True  # type: ignore
        mock_post.return_value = make_mock_response(
            status_code=200, json_data={"data": [{"embedding": vec}]}
        )

        with self.assertRaises(EmbeddingDimensionError) as ctx:
            self.client.embed("Sample text", input_type="passage")
        self.assertIn("non-numeric value of type bool", str(ctx.exception))

    # ------------------------------------------------------------------------
    # 14. Security, Privacy, and Credential Sanitization
    # ------------------------------------------------------------------------
    @patch.object(requests.Session, "post")
    def test_sanitization_no_credentials_or_raw_text_in_errors(self, mock_post):
        secret_api_key = "nvapi-SUPER-SECRET-CREDENTIAL-99999"
        secret_resume = "TOP-SECRET RESUME OF CANDIDATE JANE DOE 12345"

        secure_client = NvidiaEmbeddingClient(api_key=secret_api_key, max_retries=0)

        # 1. 401 Unauthorized
        mock_post.return_value = make_mock_response(
            status_code=401, json_data={"detail": "Bad token"}
        )
        try:
            secure_client.embed(secret_resume, input_type="passage")
        except EmbeddingAuthenticationError as err:
            err_msg = str(err)
            self.assertNotIn(secret_api_key, err_msg)
            self.assertNotIn(secret_resume, err_msg)

        # 2. 500 Server Error
        mock_post.return_value = make_mock_response(
            status_code=500, json_data={"detail": "Internal Crash"}
        )
        try:
            secure_client.embed(secret_resume, input_type="passage")
        except EmbeddingTransientError as err:
            err_msg = str(err)
            self.assertNotIn(secret_api_key, err_msg)
            self.assertNotIn(secret_resume, err_msg)

        # 3. Rate Limit
        mock_post.return_value = make_mock_response(
            status_code=429, json_data={"detail": "Too fast"}
        )
        try:
            secure_client.embed(secret_resume, input_type="passage")
        except EmbeddingRateLimitError as err:
            err_msg = str(err)
            self.assertNotIn(secret_api_key, err_msg)
            self.assertNotIn(secret_resume, err_msg)
