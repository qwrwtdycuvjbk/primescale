"""
Standalone, mockable NVIDIA NIM Embedding Client for PeopleRemotely AI Matching.

Target model: nvidia/nemotron-3-embed-1b
Embedding dimensions: exactly 2048
Input types: 'passage' (indexing documents/resumes/jobs) or 'query' (search/retrieval)
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass
from typing import Any, Final, Literal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Constants
TARGET_EMBEDDING_MODEL: Final[str] = "nvidia/nemotron-3-embed-1b"
TARGET_EMBEDDING_DIMENSIONS: Final[int] = 2048
DEFAULT_NVIDIA_API_URL: Final[str] = (
    "https://integrate.api.nvidia.com/v1/embeddings"
)

# Context limits: The official NVIDIA inference endpoint (integrate.api.nvidia.com)
# documents a maximum sequence length of 4,096 tokens for nvidia/nemotron-3-embed-1b.
# MAX_INPUT_CHARACTERS enforces a client-side character boundary, NOT a guaranteed token limit.
# Actual token counts vary based on vocabulary, language, and subword density. If a dense text
# exceeds the 4,096 token limit, NVIDIA returns HTTP 422, which is safely handled as a permanent error.
MAX_INPUT_CHARACTERS: Final[int] = 16_000


# Input type options
InputType = Literal["passage", "query"]
VALID_INPUT_TYPES: Final[frozenset[str]] = frozenset({"passage", "query"})


# ============================================================================
# Exception Hierarchy (Sanitized — never leak credentials or raw text)
# ============================================================================


class EmbeddingClientError(Exception):
    """Base exception for all embedding client errors."""

    pass


class EmbeddingConfigurationError(EmbeddingClientError):
    """Raised when required configuration (e.g. API key) is missing or invalid."""

    pass


class EmbeddingValidationError(EmbeddingClientError):
    """Raised when input text, input type, or parameters are invalid."""

    pass


class EmbeddingAuthenticationError(EmbeddingClientError):
    """Raised on HTTP 401 or 403 authentication/authorization failures."""

    pass


class EmbeddingRateLimitError(EmbeddingClientError):
    """Raised when rate limit (HTTP 429) is encountered and cannot be retried."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class EmbeddingTransientError(EmbeddingClientError):
    """Raised when transient server or network errors persist after retries."""

    pass


class EmbeddingPermanentError(EmbeddingClientError):
    """Raised on non-retryable 4xx client errors (400, 422, etc.)."""

    pass


class EmbeddingResponseError(EmbeddingClientError):
    """Raised when API returns malformed or unexpected response structure."""

    pass


class EmbeddingDimensionError(EmbeddingResponseError):
    """Raised when returned vector dimensions or values do not match requirements."""

    pass


# ============================================================================
# Result Dataclass
# ============================================================================


@dataclass(frozen=True)
class EmbeddingResult:
    """
    Immutable, predictable result object containing validated embedding vectors.
    """

    embedding: list[float]
    model: str
    input_type: str
    token_count: int | None = None
    dimensions: int = TARGET_EMBEDDING_DIMENSIONS

    def __repr__(self) -> str:
        tokens_repr = f", token_count={self.token_count}" if self.token_count is not None else ""
        return (
            f"EmbeddingResult(dimensions={len(self.embedding)}, "
            f"model='{self.model}', input_type='{self.input_type}'{tokens_repr})"
        )


# ============================================================================
# NVIDIA NIM Embedding Client
# ============================================================================


class NvidiaEmbeddingClient:
    """
    Client for generating text embeddings using NVIDIA's NeMo Retriever API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        max_retries: int | None = None,
        base_delay: float | None = None,
        max_delay: float | None = None,
        max_retry_after: float | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """
        Initialize the embedding client.

        Configuration is read from arguments or Django settings.
        Missing credentials do not raise at __init__ to avoid breaking unrelated
        Django startup/management commands; errors are raised upon invocation.
        """
        self._api_key = api_key or getattr(settings, "NVIDIA_API_KEY", "")
        self.api_url = (
            api_url
            or getattr(settings, "NVIDIA_EMBEDDING_API_URL", None)
            or DEFAULT_NVIDIA_API_URL
        )
        self.model = (
            model
            or getattr(settings, "NVIDIA_EMBEDDING_MODEL", None)
            or TARGET_EMBEDDING_MODEL
        )
        self.connect_timeout = (
            connect_timeout
            if connect_timeout is not None
            else float(getattr(settings, "NVIDIA_EMBEDDING_CONNECT_TIMEOUT", 5.0))
        )
        self.read_timeout = (
            read_timeout
            if read_timeout is not None
            else float(getattr(settings, "NVIDIA_EMBEDDING_READ_TIMEOUT", 30.0))
        )
        self.max_retries = (
            max_retries
            if max_retries is not None
            else int(getattr(settings, "NVIDIA_EMBEDDING_MAX_RETRIES", 3))
        )
        self.base_delay = (
            base_delay
            if base_delay is not None
            else float(getattr(settings, "NVIDIA_EMBEDDING_BASE_DELAY", 1.0))
        )
        self.max_delay = (
            max_delay
            if max_delay is not None
            else float(getattr(settings, "NVIDIA_EMBEDDING_MAX_DELAY", 10.0))
        )
        self.max_retry_after = (
            max_retry_after
            if max_retry_after is not None
            else float(getattr(settings, "NVIDIA_EMBEDDING_MAX_RETRY_AFTER", 15.0))
        )
        self._session = session or requests.Session()

    def _get_api_key(self) -> str:
        """Ensure an API key is available before invocation."""
        key = self._api_key or getattr(settings, "NVIDIA_API_KEY", "")
        if not key or not key.strip():
            raise EmbeddingConfigurationError(
                "NVIDIA API key is not configured. Set the NVIDIA_API_KEY environment variable."
            )
        return key.strip()

    def validate_inputs(self, text: str, input_type: str) -> None:
        """
        Validate text and input_type before dispatching requests.
        """
        if not isinstance(text, str):
            raise EmbeddingValidationError(
                f"Input text must be a string, received {type(text).__name__}."
            )

        stripped = text.strip()
        if not stripped:
            raise EmbeddingValidationError(
                "Input text cannot be empty or whitespace-only."
            )

        if len(text) > MAX_INPUT_CHARACTERS:
            raise EmbeddingValidationError(
                f"Input text length ({len(text)} characters) exceeds maximum supported "
                f"limit of {MAX_INPUT_CHARACTERS} characters."
            )

        if not isinstance(input_type, str) or input_type not in VALID_INPUT_TYPES:
            raise EmbeddingValidationError(
                f"Invalid input_type '{input_type}'. Must be either 'passage' or 'query'."
            )

    def embed(
        self,
        text: str,
        input_type: InputType,
    ) -> EmbeddingResult:
        """
        Generate a 2048-dimensional dense embedding for the given text.

        :param text: The text string to embed (resume, job description, or query).
        :param input_type: 'passage' (for indexed content) or 'query' (for search).
        :return: EmbeddingResult with exactly 2048 validated floats.
        """
        self.validate_inputs(text, input_type)
        api_key = self._get_api_key()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload: dict[str, Any] = {
            "input": [text],
            "model": self.model,
            "input_type": input_type,
            "encoding_format": "float",
            "truncate": "NONE",
        }

        attempt = 0
        last_exception: Exception | None = None

        while attempt <= self.max_retries:
            try:
                logger.debug(
                    "Sending embedding request (attempt %d/%d, chars=%d, input_type=%s, model=%s)",
                    attempt + 1,
                    self.max_retries + 1,
                    len(text),
                    input_type,
                    self.model,
                )

                response = self._session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=(self.connect_timeout, self.read_timeout),
                )

                return self._handle_response(response, input_type)

            except (EmbeddingAuthenticationError, EmbeddingPermanentError, EmbeddingValidationError):
                # Permanent errors: re-raise immediately without retry
                raise

            except EmbeddingRateLimitError as rle:
                last_exception = rle
                if attempt >= self.max_retries:
                    raise

                wait_time = rle.retry_after
                if wait_time is None:
                    wait_time = self._calculate_backoff(attempt)
                elif wait_time > self.max_retry_after:
                    raise EmbeddingRateLimitError(
                        f"NVIDIA API rate limit exceeded: Retry-After ({wait_time:.1f}s) "
                        f"exceeds maximum allowed wait ({self.max_retry_after:.1f}s)."
                    )

                logger.warning(
                    "Rate limit encountered. Waiting %.2fs before retry (attempt %d/%d)",
                    wait_time,
                    attempt + 1,
                    self.max_retries,
                )
                time.sleep(wait_time)
                attempt += 1

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
                last_exception = net_err
                if attempt >= self.max_retries:
                    raise EmbeddingTransientError(
                        f"Network/timeout error communicating with NVIDIA API after "
                        f"{self.max_retries + 1} attempts: {type(net_err).__name__}"
                    ) from net_err

                wait_time = self._calculate_backoff(attempt)
                logger.warning(
                    "Transient network error (%s). Retrying in %.2fs (attempt %d/%d)",
                    type(net_err).__name__,
                    wait_time,
                    attempt + 1,
                    self.max_retries,
                )
                time.sleep(wait_time)
                attempt += 1

            except EmbeddingTransientError as trans_err:
                last_exception = trans_err
                if attempt >= self.max_retries:
                    raise

                wait_time = self._calculate_backoff(attempt)
                logger.warning(
                    "Transient server error. Retrying in %.2fs (attempt %d/%d)",
                    wait_time,
                    attempt + 1,
                    self.max_retries,
                )
                time.sleep(wait_time)
                attempt += 1

        if last_exception:
            raise EmbeddingTransientError(
                f"Exhausted {self.max_retries} retries for embedding request."
            ) from last_exception

        raise EmbeddingTransientError("Unexpected retry loop termination.")

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff with jitter, bounded by max_delay.
        """
        backoff = min(self.base_delay * (2**attempt), self.max_delay)
        jitter = random.uniform(0.0, 0.5)
        return backoff + jitter

    def _extract_retry_after(self, response: requests.Response) -> float | None:
        """Parse Retry-After header if present."""
        retry_val = response.headers.get("Retry-After")
        if not retry_val:
            return None
        try:
            return float(retry_val)
        except (ValueError, TypeError):
            return None

    def _extract_error_detail(self, response: requests.Response) -> str:
        """Extract a sanitized, high-level error message without leaking sensitive data."""
        try:
            body = response.json()
            if isinstance(body, dict):
                # Check standard error formats
                if "detail" in body and isinstance(body["detail"], str):
                    return body["detail"][:200]
                if "error" in body:
                    err = body["error"]
                    if isinstance(err, dict) and "message" in err:
                        return str(err["message"])[:200]
                    if isinstance(err, str):
                        return err[:200]
                if "title" in body:
                    return str(body["title"])[:200]
        except Exception:
            pass
        return response.reason or f"HTTP {response.status_code}"

    def _handle_response(
        self, response: requests.Response, input_type: InputType
    ) -> EmbeddingResult:
        """
        Inspect response status code and validate response structure.
        """
        status_code = response.status_code

        # 1. Authentication / Permission errors
        if status_code in (401, 403):
            detail = self._extract_error_detail(response)
            raise EmbeddingAuthenticationError(
                f"NVIDIA API authentication failed ({status_code}): {detail}. "
                f"Verify that NVIDIA_API_KEY is valid."
            )

        # 2. Rate Limiting
        if status_code == 429:
            retry_after = self._extract_retry_after(response)
            detail = self._extract_error_detail(response)
            raise EmbeddingRateLimitError(
                f"NVIDIA API rate limit exceeded (429): {detail}",
                retry_after=retry_after,
            )

        # 3. Transient server errors
        if status_code in (500, 502, 503, 504):
            detail = self._extract_error_detail(response)
            raise EmbeddingTransientError(
                f"NVIDIA API server error ({status_code}): {detail}"
            )

        # 4. Other client errors (400, 422, etc.)
        if 400 <= status_code < 500:
            detail = self._extract_error_detail(response)
            raise EmbeddingPermanentError(
                f"NVIDIA API client request error ({status_code}): {detail}"
            )

        # 5. Other non-200 status codes
        if status_code != 200:
            detail = self._extract_error_detail(response)
            raise EmbeddingPermanentError(
                f"NVIDIA API returned unexpected status ({status_code}): {detail}"
            )

        # 6. Parse JSON payload
        try:
            data = response.json()
        except Exception as json_err:
            raise EmbeddingResponseError(
                f"NVIDIA API returned malformed JSON: {type(json_err).__name__}"
            ) from json_err

        if not isinstance(data, dict):
            raise EmbeddingResponseError(
                f"NVIDIA API response root must be a JSON object, got {type(data).__name__}."
            )

        items = data.get("data")
        if not isinstance(items, list) or len(items) == 0:
            raise EmbeddingResponseError(
                "NVIDIA API response missing non-empty 'data' array."
            )

        first_item = items[0]
        if not isinstance(first_item, dict) or "embedding" not in first_item:
            raise EmbeddingResponseError(
                "NVIDIA API response item missing 'embedding' field."
            )

        raw_vector = first_item["embedding"]
        if not isinstance(raw_vector, list):
            raise EmbeddingDimensionError(
                f"Expected embedding to be a list, got {type(raw_vector).__name__}."
            )

        # 7. Validate vector dimensionality & numeric integrity
        if len(raw_vector) != TARGET_EMBEDDING_DIMENSIONS:
            raise EmbeddingDimensionError(
                f"Dimension mismatch: expected {TARGET_EMBEDDING_DIMENSIONS} dimensions, "
                f"received {len(raw_vector)}."
            )

        validated_vector: list[float] = []
        for idx, val in enumerate(raw_vector):
            # In Python, bool is a subclass of int (isinstance(True, int) is True)
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise EmbeddingDimensionError(
                    f"Invalid embedding value at index {idx}: non-numeric value of type {type(val).__name__}."
                )
            f_val = float(val)
            if not math.isfinite(f_val):
                raise EmbeddingDimensionError(
                    f"Invalid embedding value at index {idx}: non-finite numeric value ({f_val})."
                )
            validated_vector.append(f_val)

        # 8. Extract token count if available
        token_count = None
        usage = data.get("usage")
        if isinstance(usage, dict):
            token_count = usage.get("total_tokens") or usage.get("prompt_tokens")
            if isinstance(token_count, int):
                pass
            else:
                token_count = None

        return EmbeddingResult(
            embedding=validated_vector,
            model=data.get("model") or self.model,
            input_type=input_type,
            token_count=token_count,
            dimensions=len(validated_vector),
        )
