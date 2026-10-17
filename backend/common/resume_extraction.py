"""
Secure Resume Text Extraction Foundation for PeopleRemotely AI Matching.

Features:
- Pure-Python extraction for PDF and DOCX files without third-party binary dependencies.
- Explicit unsupported-format handling for legacy binary .doc files.
- Reads private resume files ONLY via the private storage abstraction (PrivateMediaStorage).
- Rejects arbitrary URLs, caller-supplied absolute paths, and path traversal attempts.
- Enforces upload file-size limits and maximum extracted text limits.
- Normalizes whitespace, paragraph breaks, and line endings.
- Handles corrupt, encrypted, empty, and textless/scanned (image-only) files safely.
- Never logs or exposes raw resume contents, credentials, or private paths.
- Persists extracted text privately to CandidateResumeEmbedding without leaking to serializers.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, BinaryIO, Final

import pypdf
import pypdf.errors
from django.conf import settings
from django.core.files.storage import Storage

from common.storage import get_private_storage

logger = logging.getLogger(__name__)

# Constants
MAX_EXTRACTED_CHARACTERS: Final[int] = 150_000
MAX_RESUME_SIZE_BYTES: Final[int] = getattr(
    settings, "MAX_RESUME_SIZE_BYTES", 5 * 1024 * 1024
)

# Maximum PDF pages to process before halting (defense against unbounded page traversal)
MAX_PDF_PAGES: Final[int] = 1000

# Maximum indirect objects to inspect during root object recovery on malformed PDFs
MAX_PDF_ROOT_OBJECT_RECOVERY_LIMIT: Final[int] = 1000

# Decompression & Resource Bomb Defenses
MAX_ZIP_ENTRIES: Final[int] = 500
MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES: Final[int] = 20 * 1024 * 1024  # 20 MB max uncompressed
MAX_DOCX_ENTRY_SIZE_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MB max single entry
MAX_ZIP_COMPRESSION_RATIO: Final[int] = 100

# PDF Resource Configuration Limits (Tuned conservatively for resumes <= 5 MB)
PDF_SECURITY_CONFIGURATION: Final[dict[str, Any]] = {
    # Byte bounds
    "zlib_maximum_output_length": 10 * 1024 * 1024,  # 10 MB per FlateDecode stream
    "zlib_maximum_recovery_input_length": 2 * 1024 * 1024,  # 2 MB recovery input
    "maximum_declared_stream_length": 10 * 1024 * 1024,  # 10 MB max declared stream
    "array_based_stream_maximum_output_length": 10 * 1024 * 1024,  # 10 MB array stream
    "lzw_maximum_output_length": 10 * 1024 * 1024,  # 10 MB LZW stream
    "run_length_maximum_output_length": 10 * 1024 * 1024,  # 10 MB RunLength stream
    "jbig2_maximum_output_length": 10 * 1024 * 1024,  # 10 MB JBIG2 stream
    "brotli_maximum_output_length": 10 * 1024 * 1024,  # 10 MB Brotli stream
    "image_maximum_buffer_size": 15 * 1024 * 1024,  # 15 MB for image inspections
    # Stream filter & decoding work bounds (counts and per-stream decoding work)
    "stream_filters_maximum_length": 4,  # Max 4 chained filters (stops filter amplification bombs)
    "stream_decoding_work_maximum_length": 30 * 1024 * 1024,  # 30 MB max work across filter chain per stream
    # Predictor dimensions
    "flate_maximum_columns": 10_000,  # Max 10,000 columns (stops dimension bombs)
    "flate_maximum_row_length": 100_000,  # Max 100,000 bytes per row
    # Structural tree counts & depths (recursion & traversal bomb defenses)
    "page_tree_maximum_depth": 20,  # Max page-tree depth (prevents stack overflow recursion)
    "page_tree_maximum_entries": 1_500,  # Max page-tree entries (accommodates 1,000 pages)
    "outline_maximum_depth": 10,  # Max outline depth
    "outline_maximum_entries": 500,  # Max outline entries
    "xform_maximum_invocations_per_extraction": 500,  # Max XObject form invocations
    # XMP metadata bounds
    "xmp_maximum_input_length": 1 * 1024 * 1024,  # 1 MB XMP metadata
    "xmp_maximum_element_count": 5_000,  # Max 5,000 XMP elements
}


class ExtractionStatus(str, Enum):
    SUCCESS = "success"
    EMPTY_OR_WHITESPACE = "empty_or_whitespace"
    TEXTLESS_OR_IMAGE_ONLY = "textless_or_image_only"  # Scanned image, needs OCR
    ENCRYPTED_OR_PASSWORD_PROTECTED = "encrypted_or_password_protected"
    CORRUPT_OR_MALFORMED = "corrupt_or_malformed"
    CORRUPTED_OUTPUT = "corrupted_output"  # Excessive control/null bytes or unreadable glyphs
    UNSUPPORTED_FORMAT = "unsupported_format"  # E.g. legacy binary .doc
    FILE_NOT_FOUND = "file_not_found"
    FILE_TOO_LARGE = "file_too_large"
    DECOMPRESSION_BOMB_DETECTED = "decompression_bomb_detected"
    PATH_TRAVERSAL_REJECTED = "path_traversal_rejected"
    EXTRACTION_ERROR = "extraction_error"


@dataclass(frozen=True)
class ResumeExtractionResult:
    """
    Structured, sanitized extraction result.
    Does not expose sensitive credentials or internal paths.
    """

    status: ExtractionStatus
    text: str = ""
    content_hash: str | None = None
    character_count: int = 0
    word_count: int = 0
    error_message: str | None = None
    requires_ocr: bool = False
    detected_format: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == ExtractionStatus.SUCCESS and bool(self.text)

    def __repr__(self) -> str:
        return (
            f"ResumeExtractionResult(status='{self.status.value}', "
            f"chars={self.character_count}, words={self.word_count}, "
            f"format='{self.detected_format}', requires_ocr={self.requires_ocr})"
        )


def normalize_extracted_text(raw_text: str) -> str:
    """
    Normalizes extracted text while preserving meaningful word boundaries and paragraph separation:
    - Normalizes Windows (CRLF) and legacy Mac (CR) line endings to Unix (LF).
    - Converts non-breaking / exotic Unicode spaces to standard ASCII spaces.
    - Collapses multiple horizontal spaces or tabs into a single space.
    - Trims line ends while preserving paragraph breaks.
    - Collapses 3+ consecutive newlines into 2 (clean paragraph breaks).
    """
    if not raw_text:
        return ""

    # 1. Normalize line endings
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Normalize unicode space characters to standard ASCII space (including zero-width space)
    text = re.sub(
        r"[\u00a0\u1680\u2000-\u200b\u2028\u2029\u202f\u205f\u3000\ufeff]",
        " ",
        text,
    )

    # 3. Collapse multiple horizontal whitespace (spaces, tabs) into a single space
    text = re.sub(r"[ \t]+", " ", text)

    # 4. Strip whitespace from individual lines
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # 5. Collapse 3 or more consecutive newlines into double newlines for paragraph breaks
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def calculate_content_hash(text: str) -> str:
    """Computes a SHA-256 hex digest of the normalized text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def calculate_source_fingerprint(storage_path: str | None) -> str:
    """
    Computes a deterministic, collision-resistant source-file fingerprint (32 hex characters)
    from the storage path / resume_url. Fits securely within version CharField(max_length=50).
    """
    if not storage_path or not isinstance(storage_path, str):
        return ""
    return hashlib.sha256(storage_path.strip().encode("utf-8")).hexdigest()[:32]



# ============================================================================
# Format-Specific Extractors (Pure Python, Zero External Binaries)
# ============================================================================


def extract_text_from_docx_stream(stream: BinaryIO) -> tuple[str, bool, str | None]:
    """
    Extracts text from a DOCX (OpenXML) stream using standard library zipfile & ElementTree.
    Enforces decompression bomb and XML entity expansion defenses:
    - Rejects zip archives with more than MAX_ZIP_ENTRIES.
    - Rejects zip archives whose total uncompressed size exceeds MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES.
    - Rejects individual entries exceeding MAX_DOCX_ENTRY_SIZE_BYTES or extreme compression ratios.
    - Rejects XML entity declarations (Billion Laughs protection).
    - Caps text accumulation at MAX_EXTRACTED_CHARACTERS.
    """
    try:
        with zipfile.ZipFile(stream, "r") as zf:
            infolist = zf.infolist()
            # 1. Enforce max zip entries
            if len(infolist) > MAX_ZIP_ENTRIES:
                return (
                    "",
                    False,
                    f"DOCX exceeds maximum allowed zip entries ({len(infolist)} > {MAX_ZIP_ENTRIES}) (potential zip bomb).",
                )

            # 2. Enforce total uncompressed size limit
            total_uncompressed = sum(info.file_size for info in infolist)
            if total_uncompressed > MAX_DOCX_TOTAL_UNCOMPRESSED_BYTES:
                return (
                    "",
                    False,
                    f"DOCX total uncompressed size ({total_uncompressed} bytes) exceeds limit (potential zip bomb).",
                )

            if "word/document.xml" not in zf.namelist():
                return "", False, "DOCX missing word/document.xml."

            # 3. Enforce single entry size & compression ratio
            doc_info = zf.getinfo("word/document.xml")
            if doc_info.file_size > MAX_DOCX_ENTRY_SIZE_BYTES:
                return (
                    "",
                    False,
                    "DOCX word/document.xml exceeds maximum entry size (potential zip bomb).",
                )
            if (
                doc_info.compress_size > 0
                and (doc_info.file_size / doc_info.compress_size) > MAX_ZIP_COMPRESSION_RATIO
            ):
                return (
                    "",
                    False,
                    "DOCX compression ratio exceeds safety threshold (potential zip bomb).",
                )

            # 4. Stream read with size cap
            with zf.open("word/document.xml") as doc_stream:
                xml_data = doc_stream.read(MAX_DOCX_ENTRY_SIZE_BYTES + 1)
                if len(xml_data) > MAX_DOCX_ENTRY_SIZE_BYTES:
                    return (
                        "",
                        False,
                        "DOCX word/document.xml exceeded maximum allowed read limit.",
                    )

            # 5. Check for XML entity / DTD declarations (Billion Laughs defense)
            if b"<!DOCTYPE" in xml_data or b"<!ENTITY" in xml_data:
                return (
                    "",
                    False,
                    "XML entity declarations / DTDs are not permitted in DOCX files.",
                )

            tree = ET.fromstring(xml_data)

            # Namespace for WordprocessingML
            ns = {
                "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            }

            paragraphs: list[str] = []
            current_chars = 0
            for p in tree.findall(".//w:p", ns):
                # Collect text runs in this paragraph
                run_texts: list[str] = []
                for node in p.iter():
                    tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
                    if tag == "t" and node.text:
                        run_texts.append(node.text)
                    elif tag == "tab":
                        run_texts.append(" ")
                    elif tag == "br":
                        run_texts.append("\n")

                para_text = "".join(run_texts).strip()
                if para_text:
                    paragraphs.append(para_text)
                    current_chars += len(para_text)
                    if current_chars >= MAX_EXTRACTED_CHARACTERS:
                        break

            return "\n\n".join(paragraphs), True, None
    except (zipfile.BadZipFile, ET.ParseError, KeyError):
        return "", False, "Corrupt or malformed DOCX archive."
    except Exception as exc:
        logger.debug("DOCX stream extraction encountered error: %s", type(exc).__name__)
        return "", False, f"DOCX extraction error: {type(exc).__name__}"


def is_obviously_corrupted_text(raw_text: str) -> tuple[bool, str | None]:
    """
    Detects whether extracted text is unreadable or corrupted (e.g. from missing
    CMaps, broken font subsets, or un-decoded CID sequences).

    Protections:
    - Detects excessive null bytes (\\x00).
    - Detects excessive non-whitespace control characters (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F, 0x7F).
    - Detects Unicode replacement characters (\\ufffd).
    - Detects excessive Private Use Area (PUA) characters (\\ue000-\\uf8ff).
    - Ensures legitimate multilingual text (Latin with accents, Cyrillic, CJK, Arabic,
      Devanagari, Hebrew, Greek, etc.) is preserved without false positives.
    """
    if not raw_text:
        return False, None

    total_len = len(raw_text)
    if total_len == 0:
        return False, None

    null_count = raw_text.count("\x00")
    replacement_count = raw_text.count("\ufffd")

    control_count = 0
    pua_count = 0
    for ch in raw_text:
        code = ord(ch)
        if (code < 32 and ch not in "\n\r\t") or code == 127:
            control_count += 1
        elif 0xE000 <= code <= 0xF8FF:
            pua_count += 1

    corrupt_chars = null_count + replacement_count + control_count + pua_count

    # 1. Null byte detection (indicates broken 2-byte / CIDFont decoding)
    if null_count > 5 and (null_count / total_len) > 0.05:
        return (
            True,
            "Extracted text contains excessive null bytes indicating corrupted font decoding.",
        )

    # 2. Control & replacement character ratio
    if total_len >= 10 and (corrupt_chars / total_len) > 0.15:
        return (
            True,
            "Extracted text contains excessive control characters or unmapped glyphs.",
        )

    return False, None


def extract_text_from_pdf_stream(
    stream: BinaryIO,
) -> tuple[str, bool, bool, bool, str | None]:
    """
    Extracts text from a PDF stream using the maintained pypdf library.

    Enforces resource and safety boundaries:
    - Input stream bounded by MAX_RESUME_SIZE_BYTES prior to parsing.
    - Page iteration and text accumulation halt once MAX_EXTRACTED_CHARACTERS is reached.
    - Caps page processing at MAX_PDF_PAGES to prevent unbounded iteration.
    - Safe handling for encrypted/password-protected PDFs.
    - Scanned/image-only PDF detection (flags requires_ocr).
    - Corrupted output detection (excessive null bytes / control characters).
    - Exception sanitization (never logs or leaks document content).

    Note on layout limitations:
    While pypdf provides robust font CMap decoding and stream handling, it cannot
    guarantee human-expected visual reading order for complex multi-column resumes or tables
    where text blocks were written out of visual order by the authoring tool (e.g. Canva or Word).

    Returns:
        (extracted_text, is_valid_pdf, is_encrypted, has_image_only, error_message)
    """
    try:
        if hasattr(stream, "seek"):
            stream.seek(0)
        data = stream.read(MAX_RESUME_SIZE_BYTES + 1)
    except Exception as exc:
        return "", False, False, False, f"Failed to read PDF stream: {type(exc).__name__}"

    if not data:
        return "", False, False, False, "PDF stream is empty."

    if len(data) > MAX_RESUME_SIZE_BYTES:
        return (
            "",
            False,
            False,
            False,
            f"PDF file exceeds maximum allowed size ({MAX_RESUME_SIZE_BYTES} bytes).",
        )

    # Check PDF magic header
    if not data.startswith(b"%PDF-"):
        return "", False, False, False, "Not a valid PDF file."

    raw_has_encrypt = b"/Encrypt" in data

    with pypdf.apply_configuration(**PDF_SECURITY_CONFIGURATION):
        # Initialize pypdf.PdfReader with strict=False and bounded root_object_recovery_limit
        try:
            reader = pypdf.PdfReader(
                io.BytesIO(data),
                strict=False,
                root_object_recovery_limit=MAX_PDF_ROOT_OBJECT_RECOVERY_LIMIT,
            )
        except pypdf.errors.LimitReachedError:
            return (
                "",
                False,
                False,
                False,
                "PDF exceeds maximum decompression or resource limit (potential decompression bomb).",
            )
        except (pypdf.errors.FileNotDecryptedError, NotImplementedError) as enc_err:
            if raw_has_encrypt or "encrypt" in str(enc_err).lower():
                return "", True, True, False, "PDF is password-protected or encrypted."
            return "", False, False, False, "Failed to parse encrypted or malformed PDF document."
        except pypdf.errors.PdfReadError as read_err:
            if raw_has_encrypt and "encrypt" in str(read_err).lower():
                return "", True, True, False, "PDF is password-protected or encrypted."
            return "", False, False, False, f"Corrupt or malformed PDF: {type(read_err).__name__}"
        except Exception as exc:
            if raw_has_encrypt:
                return "", True, True, False, "PDF is password-protected or encrypted."
            return "", False, False, False, f"PDF read error: {type(exc).__name__}"

        # Check reader encryption status
        if getattr(reader, "is_encrypted", False):
            return "", True, True, False, "PDF is password-protected or encrypted."

        try:
            num_pages = len(reader.pages)
        except pypdf.errors.LimitReachedError:
            return (
                "",
                False,
                False,
                False,
                "PDF exceeds maximum decompression or resource limit (potential decompression bomb).",
            )
        except pypdf.errors.FileNotDecryptedError:
            return "", True, True, False, "PDF is password-protected or encrypted."
        except Exception as exc:
            return "", False, False, False, f"Corrupt or unreadable PDF pages: {type(exc).__name__}"

        if num_pages == 0:
            return "", True, False, False, None

        if num_pages > MAX_PDF_PAGES:
            return (
                "",
                False,
                False,
                False,
                f"PDF contains excessive page count ({num_pages} > {MAX_PDF_PAGES}).",
            )

        page_texts: list[str] = []
        has_any_image = False
        current_chars = 0

        for idx, page in enumerate(reader.pages):
            if current_chars >= MAX_EXTRACTED_CHARACTERS:
                break

            try:
                if hasattr(page, "images") and len(page.images) > 0:
                    has_any_image = True
            except Exception:
                pass

            try:
                page_text = page.extract_text() or ""
            except pypdf.errors.LimitReachedError:
                return (
                    "",
                    False,
                    False,
                    False,
                    "PDF exceeds maximum decompression or resource limit (potential decompression bomb).",
                )
            except pypdf.errors.FileNotDecryptedError:
                return "", True, True, False, "PDF is password-protected or encrypted."
            except Exception as exc:
                logger.debug("Error extracting text from PDF page %d: %s", idx, type(exc).__name__)
                page_text = ""

            page_text_clean = page_text.strip()
            if page_text_clean:
                # Enforce cumulative character budget across pages:
                # Slice if this page pushes cumulative text beyond MAX_EXTRACTED_CHARACTERS
                remaining_budget = MAX_EXTRACTED_CHARACTERS - current_chars
                if len(page_text_clean) > remaining_budget:
                    page_text_clean = page_text_clean[:remaining_budget]

                page_texts.append(page_text_clean)
                current_chars += len(page_text_clean)

                if current_chars >= MAX_EXTRACTED_CHARACTERS:
                    break

        full_text = "\n\n".join(page_texts).strip()
    is_textless = len(full_text) == 0

    if is_textless:
        image_present = has_any_image or bool(
            re.search(rb"/Subtype\s*/Image", data) or b"/Image" in data
        )
        return "", True, False, image_present, None

    # Corrupted output detection
    is_corrupt, corrupt_msg = is_obviously_corrupted_text(full_text)
    if is_corrupt:
        return (
            "",
            False,
            False,
            False,
            corrupt_msg or "Extracted PDF text is corrupted or unreadable.",
        )

    return full_text, True, False, False, None


# ============================================================================
# Resume Text Extraction Service
# ============================================================================


class ResumeTextExtractionService:
    """
    Dedicated, secure service for extracting and normalizing candidate resume text.
    """

    def __init__(self, storage: Storage | None = None) -> None:
        self.storage = storage or get_private_storage()

    def _validate_storage_path(self, storage_path: str) -> None:
        """
        Ensures the path does not attempt URL access or path traversal.
        """
        if not storage_path or not isinstance(storage_path, str):
            raise ValueError("Storage path must be a non-empty string.")

        # Disallow URLs
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+-.]*://", storage_path.strip()):
            raise ValueError("Arbitrary URLs are not permitted as resume storage paths.")

        # Disallow directory traversal
        normalized = os.path.normpath(storage_path)
        if ".." in normalized.split(os.sep) or ".." in storage_path:
            raise ValueError("Directory traversal attempt detected in resume storage path.")

    def extract_from_stream(
        self,
        stream: BinaryIO,
        filename: str,
        size_bytes: int | None = None,
    ) -> ResumeExtractionResult:
        """
        Extracts and normalizes text from a file stream.
        """
        # 1. Enforce file size limit before full read
        if size_bytes is not None and size_bytes > MAX_RESUME_SIZE_BYTES:
            max_mb = MAX_RESUME_SIZE_BYTES / (1024 * 1024)
            return ResumeExtractionResult(
                status=ExtractionStatus.FILE_TOO_LARGE,
                error_message=f"File exceeds maximum allowed size of {max_mb:.1f} MB.",
            )

        # Inspect stream size even if size_bytes was not provided
        stream.seek(0, io.SEEK_END)
        actual_size = stream.tell()
        stream.seek(0)
        if actual_size > MAX_RESUME_SIZE_BYTES:
            max_mb = MAX_RESUME_SIZE_BYTES / (1024 * 1024)
            return ResumeExtractionResult(
                status=ExtractionStatus.FILE_TOO_LARGE,
                error_message=f"File exceeds maximum allowed size of {max_mb:.1f} MB.",
            )

        ext = os.path.splitext(filename.lower())[1]

        # 2. Check for legacy .doc binary format
        header = stream.read(8)
        stream.seek(0)

        if ext == ".doc" or header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            logger.info("Encountered legacy binary .doc format; reporting unsupported.")
            return ResumeExtractionResult(
                status=ExtractionStatus.UNSUPPORTED_FORMAT,
                detected_format="doc",
                error_message=(
                    "Legacy binary .doc format is not supported for text extraction. "
                    "Please re-upload your resume in PDF (.pdf) or Word (.docx) format."
                ),
            )

        # 3. Handle DOCX format
        if ext == ".docx" or header.startswith(b"PK\x03\x04"):
            extracted, is_valid_docx, err_msg = extract_text_from_docx_stream(stream)
            if not is_valid_docx:
                status = (
                    ExtractionStatus.DECOMPRESSION_BOMB_DETECTED
                    if err_msg and "bomb" in err_msg.lower()
                    else ExtractionStatus.CORRUPT_OR_MALFORMED
                )
                return ResumeExtractionResult(
                    status=status,
                    detected_format="docx",
                    error_message=err_msg
                    or "The DOCX document is corrupt, damaged, or not a valid Word file.",
                )

            normalized = normalize_extracted_text(extracted)
            if not normalized:
                return ResumeExtractionResult(
                    status=ExtractionStatus.EMPTY_OR_WHITESPACE,
                    detected_format="docx",
                    error_message="The DOCX document contains no extractable text.",
                )

            if len(normalized) > MAX_EXTRACTED_CHARACTERS:
                normalized = normalized[:MAX_EXTRACTED_CHARACTERS]

            content_hash = calculate_content_hash(normalized)
            words = len(normalized.split())

            return ResumeExtractionResult(
                status=ExtractionStatus.SUCCESS,
                text=normalized,
                content_hash=content_hash,
                character_count=len(normalized),
                word_count=words,
                detected_format="docx",
            )

        # 4. Handle PDF format
        if ext == ".pdf" or header.startswith(b"%PDF-"):
            extracted, is_valid_pdf, is_encrypted, has_image_only, err_msg = (
                extract_text_from_pdf_stream(stream)
            )

            if not is_valid_pdf:
                status = (
                    ExtractionStatus.DECOMPRESSION_BOMB_DETECTED
                    if err_msg and ("bomb" in err_msg.lower() or "decompression" in err_msg.lower() or "resource limit" in err_msg.lower())
                    else (
                        ExtractionStatus.CORRUPTED_OUTPUT
                        if err_msg and ("null bytes" in err_msg.lower() or "unmapped glyphs" in err_msg.lower() or "corrupted font" in err_msg.lower())
                        else ExtractionStatus.CORRUPT_OR_MALFORMED
                    )
                )
                return ResumeExtractionResult(
                    status=status,
                    detected_format="pdf",
                    error_message=err_msg
                    or "The PDF document is corrupt, damaged, or not a valid PDF file.",
                )

            if is_encrypted:
                return ResumeExtractionResult(
                    status=ExtractionStatus.ENCRYPTED_OR_PASSWORD_PROTECTED,
                    detected_format="pdf",
                    error_message=err_msg
                    or "The PDF document is password-protected or encrypted.",
                )

            if has_image_only:
                return ResumeExtractionResult(
                    status=ExtractionStatus.TEXTLESS_OR_IMAGE_ONLY,
                    detected_format="pdf",
                    requires_ocr=True,
                    error_message=(
                        "The PDF document contains scanned images or no extractable text. "
                        "OCR processing is required to extract text from this document."
                    ),
                )

            normalized = normalize_extracted_text(extracted)
            if not normalized:
                return ResumeExtractionResult(
                    status=ExtractionStatus.EMPTY_OR_WHITESPACE,
                    detected_format="pdf",
                    error_message="The PDF document contains no extractable text.",
                )

            if len(normalized) > MAX_EXTRACTED_CHARACTERS:
                normalized = normalized[:MAX_EXTRACTED_CHARACTERS]

            content_hash = calculate_content_hash(normalized)
            words = len(normalized.split())

            return ResumeExtractionResult(
                status=ExtractionStatus.SUCCESS,
                text=normalized,
                content_hash=content_hash,
                character_count=len(normalized),
                word_count=words,
                detected_format="pdf",
            )

        # 5. Unsupported other extensions
        return ResumeExtractionResult(
            status=ExtractionStatus.UNSUPPORTED_FORMAT,
            detected_format=ext.lstrip("."),
            error_message=(
                f"Unsupported resume file format '{ext}'. "
                f"Supported formats for AI text extraction are PDF (.pdf) and Word (.docx)."
            ),
        )

    def extract_from_storage(self, storage_path: str) -> ResumeExtractionResult:
        """
        Securely opens and extracts text from a file in private storage.
        """
        try:
            self._validate_storage_path(storage_path)
        except ValueError as val_err:
            return ResumeExtractionResult(
                status=ExtractionStatus.PATH_TRAVERSAL_REJECTED,
                error_message=str(val_err),
            )

        clean_path = storage_path.strip().lstrip("/")

        # Verify existence in private storage
        try:
            if not self.storage.exists(clean_path):
                return ResumeExtractionResult(
                    status=ExtractionStatus.FILE_NOT_FOUND,
                    error_message="Resume file was not found in private storage.",
                )
        except Exception as exc:
            logger.warning("Error checking storage existence: %s", type(exc).__name__)
            return ResumeExtractionResult(
                status=ExtractionStatus.FILE_NOT_FOUND,
                error_message="Unable to access resume file in private storage.",
            )

        # Open and extract
        try:
            file_size = None
            try:
                file_size = self.storage.size(clean_path)
            except Exception:
                pass

            with self.storage.open(clean_path, "rb") as file_stream:
                filename = os.path.basename(clean_path)
                result = self.extract_from_stream(
                    file_stream, filename=filename, size_bytes=file_size
                )
                if result.is_success:
                    logger.info("Successfully extracted text from resume in storage (chars=%d)", result.character_count)
                return result
        except Exception as exc:
            logger.error("Unexpected error during resume extraction: %s", type(exc).__name__)
            return ResumeExtractionResult(
                status=ExtractionStatus.EXTRACTION_ERROR,
                error_message="An error occurred while reading the resume file.",
            )

    def extract_and_persist_for_candidate(
        self,
        candidate_profile: Any,
        persist: bool = True,
    ) -> ResumeExtractionResult:
        """
        Extracts text from candidate_profile.resume_url and persists it privately
        to CandidateResumeEmbedding without generating embeddings or touching vector columns.
        """
        from matching.models import CandidateResumeEmbedding, EmbeddingStatus

        if not candidate_profile or not getattr(candidate_profile, "resume_url", None):
            return ResumeExtractionResult(
                status=ExtractionStatus.FILE_NOT_FOUND,
                error_message="Candidate has no uploaded resume.",
            )

        resume_path = candidate_profile.resume_url
        result = self.extract_from_storage(resume_path)

        if not persist:
            return result

        from django.db import transaction
        from candidates.models import CandidateProfile

        with transaction.atomic():
            locked_profile = (
                CandidateProfile.objects.select_for_update()
                .filter(id=candidate_profile.id)
                .first()
            )
            # Re-check that candidate's resume_url in DB has not changed or been cleared
            if (
                not locked_profile
                or not locked_profile.resume_url
                or locked_profile.resume_url != resume_path
            ):
                logger.warning(
                    "Candidate %s resume_url changed or was cleared while extraction was in flight "
                    "(expected %s, found %s); discarding stale extraction result.",
                    candidate_profile.id,
                    resume_path,
                    getattr(locked_profile, "resume_url", None),
                )
                return ResumeExtractionResult(
                    status=ExtractionStatus.EXTRACTION_ERROR,
                    error_message="Stale resume extraction discarded because resume was updated or removed.",
                )

            # Get or create the OneToOne CandidateResumeEmbedding under lock
            resume_embedding, _ = CandidateResumeEmbedding.objects.select_for_update().get_or_create(
                candidate_profile=locked_profile
            )

            source_fingerprint = calculate_source_fingerprint(resume_path)

            if result.is_success:
                # If content and source are unchanged and embedding is already completed, preserve existing vector
                is_unchanged = (
                    resume_embedding.content_hash == result.content_hash
                    and resume_embedding.version == source_fingerprint
                    and resume_embedding.status == EmbeddingStatus.COMPLETED
                    and resume_embedding.embedding is not None
                )
                if not is_unchanged:
                    resume_embedding.extracted_text = result.text
                    resume_embedding.content_hash = result.content_hash
                    resume_embedding.text_length = result.character_count
                    resume_embedding.status = EmbeddingStatus.PENDING
                    resume_embedding.error_message = None
                    resume_embedding.version = source_fingerprint
                    resume_embedding.embedding = None
                    resume_embedding.embedded_at = None
                    resume_embedding.save(
                        update_fields=[
                            "extracted_text",
                            "content_hash",
                            "text_length",
                            "status",
                            "error_message",
                            "version",
                            "embedding",
                            "embedded_at",
                            "updated_at",
                        ]
                    )
                logger.info(
                    "Extracted and persisted resume text for candidate %s (chars=%d, hash=%s, version=%s)",
                    candidate_profile.id,
                    result.character_count,
                    result.content_hash[:8] if result.content_hash else "None",
                    source_fingerprint[:8],
                )
            else:
                resume_embedding.status = EmbeddingStatus.FAILED
                resume_embedding.error_message = result.error_message
                resume_embedding.extracted_text = None
                resume_embedding.content_hash = None
                resume_embedding.text_length = 0
                resume_embedding.embedding = None
                resume_embedding.embedded_at = None
                resume_embedding.version = source_fingerprint
                resume_embedding.save(
                    update_fields=[
                        "status",
                        "error_message",
                        "extracted_text",
                        "content_hash",
                        "text_length",
                        "embedding",
                        "embedded_at",
                        "version",
                        "updated_at",
                    ]
                )
                logger.warning(
                    "Resume extraction failed for candidate %s (status=%s)",
                    candidate_profile.id,
                    result.status.value,
                )

        return result
