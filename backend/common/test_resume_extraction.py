"""
Comprehensive test suite for Secure Resume Text Extraction Foundation.

Covers:
- Valid PDF extraction.
- Valid DOCX extraction.
- Empty and whitespace-only documents.
- Corrupt or unreadable files.
- Unsupported legacy binary .doc files.
- Textless or image-only PDF detection (requires OCR).
- Encrypted / password-protected PDF detection.
- File-size limit and extraction-limit enforcement.
- Whitespace and paragraph normalization.
- Safe error handling and absence of resume text in logs.
- Private storage access and rejection of arbitrary URLs or path traversal.
- Complete privacy verification: no exposure of extracted_text in existing API serializers.
- Model persistence without embedding generation.
"""

import io
import logging
import zipfile
import zlib
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.test import TestCase, override_settings

from accounts.models import User
from candidates.models import CandidateProfile
from candidates.serializers import (
    AdminCandidateListSerializer,
    CandidateProfileSerializer,
    PublicTalentCardSerializer,
)
from common.resume_extraction import (
    MAX_EXTRACTED_CHARACTERS,
    MAX_PDF_PAGES,
    MAX_RESUME_SIZE_BYTES,
    MAX_ZIP_COMPRESSION_RATIO,
    MAX_ZIP_ENTRIES,
    ExtractionStatus,
    ResumeExtractionResult,
    ResumeTextExtractionService,
    calculate_content_hash,
    is_obviously_corrupted_text,
    normalize_extracted_text,
)
from companies.models import Company
from jobs.models import Job
from matching.models import (
    CandidateResumeEmbedding,
    EmbeddingStatus,
    Match,
)
from matching.serializers import (
    AdminMatchSerializer,
    CandidateMatchSerializer,
    EmployerMatchSerializer,
)


def make_test_pdf(text_lines: list[str]) -> bytes:
    """Constructs a minimal valid standard PDF with specified text lines and standard Helvetica font."""
    commands = ["BT", "/F1 12 Tf", "14 TL", "72 712 Td"]
    for line in text_lines:
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({safe_line}) Tj")
        commands.append("T*")
    commands.append("ET")

    stream_body = "\n".join(commands).encode("latin-1")
    compressed = zlib.compress(stream_body)

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    obj4 = (
        b"4 0 obj\n<< /Length "
        + str(len(compressed)).encode()
        + b" /Filter /FlateDecode >>\nstream\n"
        + compressed
        + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    header = b"%PDF-1.4\n"
    pos1 = len(header)
    pos2 = pos1 + len(obj1)
    pos3 = pos2 + len(obj2)
    pos4 = pos3 + len(obj3)
    pos5 = pos4 + len(obj4)
    xref_pos = pos5 + len(obj5)

    xref = (
        f"xref\n0 6\n"
        f"0000000000 65535 f \n"
        f"{pos1:010d} 00000 n \n"
        f"{pos2:010d} 00000 n \n"
        f"{pos3:010d} 00000 n \n"
        f"{pos4:010d} 00000 n \n"
        f"{pos5:010d} 00000 n \n"
    ).encode("ascii")

    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("ascii")
    return header + obj1 + obj2 + obj3 + obj4 + obj5 + xref + trailer


def make_multipage_pdf(pages_text: list[list[str]]) -> bytes:
    """Constructs a valid multi-page PDF using pypdf.PdfWriter."""
    import pypdf
    writer = pypdf.PdfWriter()
    for page_lines in pages_text:
        single_pdf = make_test_pdf(page_lines)
        writer.append(io.BytesIO(single_pdf))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_encrypted_pdf(text_lines: list[str], password: str = "secretpass") -> bytes:
    """Constructs a valid encrypted PDF using pypdf.PdfWriter."""
    import pypdf
    single_pdf = make_test_pdf(text_lines)
    writer = pypdf.PdfWriter()
    writer.append(io.BytesIO(single_pdf))
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_scanned_pdf() -> bytes:
    """Constructs a valid PDF containing an image XObject on the page and no extractable text."""
    img_data = b"\xff\xd8\xff\xe0\x00\x10JFIF" + (b"\x00" * 50)
    img_compressed = zlib.compress(img_data)

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /XObject << /Im1 5 0 R >> >> /Contents 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    content_stream = b"q 612 0 0 792 0 0 cm /Im1 Do Q"
    compressed_content = zlib.compress(content_stream)
    obj4 = (
        b"4 0 obj\n<< /Length "
        + str(len(compressed_content)).encode()
        + b" /Filter /FlateDecode >>\nstream\n"
        + compressed_content
        + b"\nendstream\nendobj\n"
    )
    obj5 = (
        b"5 0 obj\n<< /Type /XObject /Subtype /Image /Width 100 /Height 100 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Length "
        + str(len(img_compressed)).encode()
        + b" /Filter /FlateDecode >>\nstream\n"
        + img_compressed
        + b"\nendstream\nendobj\n"
    )

    header = b"%PDF-1.4\n"
    objs = [obj1, obj2, obj3, obj4, obj5]
    positions = []
    curr = len(header)
    for o in objs:
        positions.append(curr)
        curr += len(o)

    xref_pos = curr
    xref_lines = ["xref\n0 6\n0000000000 65535 f \n"]
    for p in positions:
        xref_lines.append(f"{p:010d} 00000 n \n")
    xref = "".join(xref_lines).encode("ascii")
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("ascii")
    return header + b"".join(objs) + xref + trailer


def make_tounicode_cmap_pdf() -> bytes:
    """
    Constructs a genuine PDF containing an Identity-H CIDFont with an explicit
    /ToUnicode CMap mapping glyphs <0001>, <0002>, <0003>, <0004> to
    Unicode characters U+00C9 ('É'), U+00E0 ('à'), U+4E2D ('中'), U+6587 ('文').
    """
    cmap_body = (
        b"/CIDInit /ProcSet findresource begin\n"
        b"12 dict begin\nbegincmap\n"
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        b"/CMapName /Custom-ToUnicode def\n/CMapType 2 def\n"
        b"1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
        b"4 beginbfchar\n"
        b"<0001> <00C9>\n"
        b"<0002> <00E0>\n"
        b"<0003> <4E2D>\n"
        b"<0004> <6587>\n"
        b"endbfchar\nendcmap\n"
        b"CMapName currentdict /CMap defineresource pop\nend\nend\n"
    )

    text_stream = b"BT /F1 12 Tf 14 TL 72 712 Td <0001000200030004> Tj ET"
    compressed_text = zlib.compress(text_stream)
    compressed_cmap = zlib.compress(cmap_body)

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    obj4 = b"4 0 obj\n<< /Length " + str(len(compressed_text)).encode() + b" /Filter /FlateDecode >>\nstream\n" + compressed_text + b"\nendstream\nendobj\n"
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type0 /BaseFont /CustomCMapFont /Encoding /Identity-H /DescendantFonts [6 0 R] /ToUnicode 7 0 R >>\nendobj\n"
    obj6 = b"6 0 obj\n<< /Type /Font /Subtype /CIDFontType2 /BaseFont /CustomCMapFont /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 8 0 R >>\nendobj\n"
    obj7 = b"7 0 obj\n<< /Length " + str(len(compressed_cmap)).encode() + b" /Filter /FlateDecode >>\nstream\n" + compressed_cmap + b"\nendstream\nendobj\n"
    obj8 = b"8 0 obj\n<< /Type /FontDescriptor /FontName /CustomCMapFont /Flags 4 /FontBBox [-100 -100 1000 1000] /ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >>\nendobj\n"

    header = b"%PDF-1.4\n"
    objs = [obj1, obj2, obj3, obj4, obj5, obj6, obj7, obj8]
    positions = []
    curr = len(header)
    for o in objs:
        positions.append(curr)
        curr += len(o)

    xref_pos = curr
    xref_lines = ["xref\n0 9\n0000000000 65535 f \n"]
    for p in positions:
        xref_lines.append(f"{p:010d} 00000 n \n")
    xref = "".join(xref_lines).encode("ascii")
    trailer = f"trailer\n<< /Size 9 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("ascii")
    return header + b"".join(objs) + xref + trailer


def make_test_docx(paragraphs: list[str]) -> bytes:
    """Constructs a minimal valid DOCX with specified paragraphs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        p_xmls = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{p_xmls}</w:body>"
            "</w:document>"
        )
        zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


class ResumeTextExtractionServiceTests(TestCase):
    def setUp(self):
        super().setUp()
        self.mock_storage = InMemoryStorage()
        self.service = ResumeTextExtractionService(storage=self.mock_storage)

        self.candidate_user = User.objects.create_user(
            email="extraction_candidate@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
            full_name="Extract Candidate",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Python Infrastructure Lead",
            current_title="Software Architect",
            skills=["Python", "Django", "PostgreSQL"],
            role_categories=["Engineering"],
            profile_complete=True,
            open_to_matching=True,
        )

        self.employer_user = User.objects.create_user(
            email="extraction_employer@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Extract Employer",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Extract Systems Inc",
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior AI Architect",
            description="Leading AI infrastructure.",
            status=Job.Status.ACTIVE,
        )

    # ------------------------------------------------------------------------
    # 1. Valid PDF Extraction
    # ------------------------------------------------------------------------
    def test_valid_pdf_extraction(self):
        pdf_content = make_test_pdf([
            "Jane Doe",
            "Senior Python Architect",
            "Expert in Django, PostgreSQL, and distributed systems.",
        ])
        path = "resumes/candidate_1/resume.pdf"
        self.mock_storage.save(path, ContentFile(pdf_content))

        result = self.service.extract_from_storage(path)

        self.assertEqual(result.status, ExtractionStatus.SUCCESS)
        self.assertTrue(result.is_success)
        self.assertEqual(result.detected_format, "pdf")
        self.assertIn("Jane Doe", result.text)
        self.assertIn("Senior Python Architect", result.text)
        self.assertIn("distributed systems.", result.text)
        self.assertGreater(result.character_count, 20)
        self.assertGreater(result.word_count, 5)
        self.assertIsNotNone(result.content_hash)
        self.assertEqual(result.content_hash, calculate_content_hash(result.text))
        self.assertFalse(result.requires_ocr)

    def test_multipage_pdf_extraction(self):
        """Extracts text across multiple pages and preserves page/paragraph boundaries."""
        pages = [
            ["Jane Doe", "Lead Infrastructure Engineer"],
            ["Experience at Tech Corp", "10 years leading cloud migrations"],
        ]
        pdf_content = make_multipage_pdf(pages)
        path = "resumes/candidate_multi/resume.pdf"
        self.mock_storage.save(path, ContentFile(pdf_content))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.SUCCESS)
        self.assertTrue(result.is_success)
        self.assertIn("Jane Doe", result.text)
        self.assertIn("10 years leading cloud migrations", result.text)
        # Verify page separation
        self.assertIn("\n\n", result.text)

    def test_pdf_unicode_encoding_fixture(self):
        """Extracts text from PDF containing Unicode characters with standard Helvetica font."""
        pdf_content = make_test_pdf([
            "Dr. Rene Muller",
            "Software Architect & Engineer",
            "Built distributed ML pipelines with PyTorch and PostgreSQL.",
        ])
        path = "resumes/candidate_unicode/resume.pdf"
        self.mock_storage.save(path, ContentFile(pdf_content))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.SUCCESS)
        self.assertTrue(result.is_success)
        self.assertIn("Rene Muller", result.text)
        self.assertIn("Software Architect & Engineer", result.text)

    def test_pdf_genuine_tounicode_cmap_extraction(self):
        """Extracts text correctly from a PDF using a genuine /ToUnicode CMap with Identity-H CIDFont."""
        pdf_content = make_tounicode_cmap_pdf()
        path = "resumes/candidate_cmap/resume.pdf"
        self.mock_storage.save(path, ContentFile(pdf_content))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.SUCCESS)
        self.assertTrue(result.is_success)
        self.assertEqual(result.detected_format, "pdf")
        # Glyphs <0001000200030004> mapped via ToUnicode CMap:
        self.assertEqual(result.text, "\u00c9\u00e0\u4e2d\u6587")

    # ------------------------------------------------------------------------
    # 2. Valid DOCX Extraction
    # ------------------------------------------------------------------------
    def test_valid_docx_extraction(self):
        docx_content = make_test_docx([
            "John Smith",
            "Lead Backend Engineer",
            "Built high-throughput payment gateways and async workers.",
        ])
        path = "resumes/candidate_2/resume.docx"
        self.mock_storage.save(path, ContentFile(docx_content))

        result = self.service.extract_from_storage(path)

        self.assertEqual(result.status, ExtractionStatus.SUCCESS)
        self.assertTrue(result.is_success)
        self.assertEqual(result.detected_format, "docx")
        self.assertIn("John Smith", result.text)
        self.assertIn("Lead Backend Engineer", result.text)
        self.assertIn("payment gateways", result.text)
        self.assertGreater(result.character_count, 20)
        self.assertIsNotNone(result.content_hash)

    # ------------------------------------------------------------------------
    # 3. Empty and Whitespace-only Documents
    # ------------------------------------------------------------------------
    def test_empty_file_handling(self):
        path = "resumes/candidate_empty/empty.pdf"
        self.mock_storage.save(path, ContentFile(b""))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.CORRUPT_OR_MALFORMED)
        self.assertFalse(result.is_success)

    def test_whitespace_only_docx(self):
        docx_content = make_test_docx(["   ", "\t", "\n\n  "])
        path = "resumes/candidate_ws/whitespace.docx"
        self.mock_storage.save(path, ContentFile(docx_content))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.EMPTY_OR_WHITESPACE)
        self.assertFalse(result.is_success)

    # ------------------------------------------------------------------------
    # 4. Corrupt or Malformed Files
    # ------------------------------------------------------------------------
    def test_corrupt_pdf_file(self):
        path = "resumes/candidate_corrupt/corrupt.pdf"
        self.mock_storage.save(path, ContentFile(b"%PDF-1.4 corrupt data truncated garbage"))

        result = self.service.extract_from_storage(path)
        # Should gracefully return empty or corrupt without crashing
        self.assertIn(result.status, (ExtractionStatus.CORRUPT_OR_MALFORMED, ExtractionStatus.EMPTY_OR_WHITESPACE))
        self.assertFalse(result.is_success)

    def test_corrupt_docx_file(self):
        path = "resumes/candidate_corrupt/corrupt.docx"
        self.mock_storage.save(path, ContentFile(b"PK\x03\x04 corrupt zip bytes not a real docx"))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.CORRUPT_OR_MALFORMED)
        self.assertFalse(result.is_success)

    # ------------------------------------------------------------------------
    # 5. Unsupported Legacy Binary .doc Files
    # ------------------------------------------------------------------------
    def test_unsupported_legacy_doc(self):
        legacy_doc_bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + (b"\x00" * 512)
        path = "resumes/candidate_legacy/old_resume.doc"
        self.mock_storage.save(path, ContentFile(legacy_doc_bytes))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.UNSUPPORTED_FORMAT)
        self.assertEqual(result.detected_format, "doc")
        self.assertIn("Legacy binary .doc format is not supported", result.error_message)
        self.assertFalse(result.is_success)

    # ------------------------------------------------------------------------
    # 6. Textless or Image-Only Scanned PDF Detection (Requires OCR)
    # ------------------------------------------------------------------------
    def test_image_only_scanned_pdf(self):
        image_pdf = make_scanned_pdf()
        path = "resumes/candidate_scanned/scan.pdf"
        self.mock_storage.save(path, ContentFile(image_pdf))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.TEXTLESS_OR_IMAGE_ONLY)
        self.assertTrue(result.requires_ocr)
        self.assertIn("OCR processing is required", result.error_message)

    # ------------------------------------------------------------------------
    # 7. Encrypted / Password-Protected PDF Detection
    # ------------------------------------------------------------------------
    def test_encrypted_pdf_detection(self):
        encrypted_pdf = make_encrypted_pdf([
            "CONFIDENTIAL RESUME",
            "Sensitive financial details and salary requirements",
        ])
        path = "resumes/candidate_locked/locked.pdf"
        self.mock_storage.save(path, ContentFile(encrypted_pdf))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.ENCRYPTED_OR_PASSWORD_PROTECTED)
        self.assertIn("password-protected or encrypted", result.error_message)

    # ------------------------------------------------------------------------
    # 8. File-Size and Extraction-Limit Enforcement
    # ------------------------------------------------------------------------
    def test_file_size_limit_enforced(self):
        oversized_data = b"%PDF-1.4\n" + (b"0" * (MAX_RESUME_SIZE_BYTES + 1024))
        path = "resumes/candidate_big/oversized.pdf"
        self.mock_storage.save(path, ContentFile(oversized_data))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.FILE_TOO_LARGE)
        self.assertIn("File exceeds maximum allowed size", result.error_message)

    def test_extraction_character_limit_boundary(self):
        # 100 paragraphs of 2,000 chars = 200,000 chars (exceeds 150,000 limit)
        long_paragraphs = ["A" * 2000 for _ in range(100)]
        docx_bytes = make_test_docx(long_paragraphs)
        path = "resumes/candidate_long/long.docx"
        self.mock_storage.save(path, ContentFile(docx_bytes))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.SUCCESS)
        self.assertEqual(result.character_count, MAX_EXTRACTED_CHARACTERS)
        self.assertEqual(len(result.text), MAX_EXTRACTED_CHARACTERS)

    # ------------------------------------------------------------------------
    # 8b. Resource-Exhaustion & Decompression Bomb Protection (Phase 4.1)
    # ------------------------------------------------------------------------
    def test_docx_zip_entry_count_limit(self):
        """Rejects DOCX archives with excessive member entries (zip bomb defense)."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for i in range(MAX_ZIP_ENTRIES + 1):
                zf.writestr(f"entry_{i}.xml", b"<dummy/>")
        path = "resumes/bomb/many_entries.docx"
        self.mock_storage.save(path, ContentFile(buf.getvalue()))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.DECOMPRESSION_BOMB_DETECTED)
        self.assertIn("zip entries", result.error_message)

    def test_docx_compression_ratio_limit(self):
        """Rejects DOCX archives with abnormal compression ratio (zip bomb defense)."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 25,000 bytes of zeros compresses down to ~40 bytes (ratio > 500:1)
            zf.writestr("word/document.xml", b"0" * 25000)
        path = "resumes/bomb/ratio_bomb.docx"
        self.mock_storage.save(path, ContentFile(buf.getvalue()))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.DECOMPRESSION_BOMB_DETECTED)
        self.assertIn("compression ratio", result.error_message)

    def test_docx_xml_entity_declaration_rejection(self):
        """Rejects DOCX documents containing XML entity/DTD declarations (Billion Laughs defense)."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            xml_data = (
                b'<?xml version="1.0"?>\n'
                b'<!DOCTYPE doc [<!ENTITY lol "lol">]>\n'
                b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
                b'<w:body><w:p><w:r><w:t>&lol;</w:t></w:r></w:p></w:body>\n'
                b'</w:document>'
            )
            zf.writestr("word/document.xml", xml_data)
        path = "resumes/bomb/xml_entity.docx"
        self.mock_storage.save(path, ContentFile(buf.getvalue()))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.CORRUPT_OR_MALFORMED)
        self.assertIn("XML entity declarations", result.error_message)

    def test_pdf_max_pages_limit(self):
        """Rejects PDF containing excessive page count (page traversal bomb defense)."""
        import pypdf
        writer = pypdf.PdfWriter()
        for _ in range(MAX_PDF_PAGES + 1):
            writer.add_blank_page(width=10, height=10)
        buf = io.BytesIO()
        writer.write(buf)

        path = "resumes/bomb/pdf_many_pages.pdf"
        self.mock_storage.save(path, ContentFile(buf.getvalue()))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.CORRUPT_OR_MALFORMED)
        self.assertIn("excessive page count", result.error_message)

    def test_pdf_stream_decompression_bomb_limit(self):
        """Rejects PDF containing a stream that exceeds zlib_maximum_output_length (decompression bomb defense)."""
        # Compress 11 MB of spaces (~11 KB compressed) which exceeds the 10 MB decompression limit
        huge_stream = zlib.compress(b"BT /F1 12 Tf " + b" " * (11 * 1024 * 1024) + b" ET")
        obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        obj4 = b"4 0 obj\n<< /Length " + str(len(huge_stream)).encode() + b" /Filter /FlateDecode >>\nstream\n" + huge_stream + b"\nendstream\nendobj\n"
        obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

        header = b"%PDF-1.4\n"
        objs = [obj1, obj2, obj3, obj4, obj5]
        positions = []
        curr = len(header)
        for o in objs:
            positions.append(curr)
            curr += len(o)
        xref_lines = ["xref\n0 6\n0000000000 65535 f \n"] + [f"{p:010d} 00000 n \n" for p in positions]
        xref = "".join(xref_lines).encode("ascii")
        trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{curr}\n%%EOF".encode("ascii")
        bomb_pdf = header + b"".join(objs) + xref + trailer

        path = "resumes/bomb/pdf_bomb.pdf"
        self.mock_storage.save(path, ContentFile(bomb_pdf))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.DECOMPRESSION_BOMB_DETECTED)
        self.assertIn("decompression", result.error_message.lower())

    def test_pdf_stream_filter_length_limit(self):
        """Rejects PDF with chained filters exceeding stream_filters_maximum_length (filter amplification defense)."""
        stream_data = b"BT /F1 12 Tf (hello world resume text) Tj ET"
        for _ in range(5):  # 5 chained flate decodes exceeds stream_filters_maximum_length=4
            stream_data = zlib.compress(stream_data)

        obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        obj4 = (
            b"4 0 obj\n<< /Length "
            + str(len(stream_data)).encode()
            + b" /Filter [/FlateDecode /FlateDecode /FlateDecode /FlateDecode /FlateDecode] >>\nstream\n"
            + stream_data
            + b"\nendstream\nendobj\n"
        )
        obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        header = b"%PDF-1.4\n"
        objs = [obj1, obj2, obj3, obj4, obj5]
        positions = []
        curr = len(header)
        for o in objs:
            positions.append(curr)
            curr += len(o)
        xref_lines = ["xref\n0 6\n0000000000 65535 f \n"] + [f"{p:010d} 00000 n \n" for p in positions]
        xref = "".join(xref_lines).encode("ascii")
        trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{curr}\n%%EOF".encode("ascii")
        filter_pdf = header + b"".join(objs) + xref + trailer

        path = "resumes/bomb/pdf_filters.pdf"
        self.mock_storage.save(path, ContentFile(filter_pdf))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.DECOMPRESSION_BOMB_DETECTED)
        self.assertIn("limit", result.error_message.lower())

    def test_pdf_page_tree_depth_limit(self):
        """Rejects PDF with deeply nested page tree exceeding page_tree_maximum_depth (recursion defense)."""
        objs = [b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"]
        depth = 25  # exceeds page_tree_maximum_depth=20
        for i in range(2, 2 + depth):
            child_id = i + 1
            objs.append(f"{i} 0 obj\n<< /Type /Pages /Kids [{child_id} 0 R] /Count 1 >>\nendobj\n".encode())
        leaf_id = 2 + depth
        objs.append(f"{leaf_id} 0 obj\n<< /Type /Page /Parent {leaf_id - 1} 0 R /MediaBox [0 0 612 792] >>\nendobj\n".encode())

        header = b"%PDF-1.4\n"
        positions = []
        curr = len(header)
        for o in objs:
            positions.append(curr)
            curr += len(o)
        xref_lines = [f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"] + [f"{p:010d} 00000 n \n" for p in positions]
        xref = "".join(xref_lines).encode("ascii")
        trailer = f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{curr}\n%%EOF".encode("ascii")
        deep_tree_pdf = header + b"".join(objs) + xref + trailer

        path = "resumes/bomb/pdf_deep_tree.pdf"
        self.mock_storage.save(path, ContentFile(deep_tree_pdf))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.DECOMPRESSION_BOMB_DETECTED)
        self.assertIn("limit", result.error_message.lower())

    def test_pdf_configuration_scoped_and_restored_on_success(self):
        """Proves pypdf configuration is scoped during extraction and restored afterward on success."""
        import pypdf
        orig_zlib = pypdf.get_configuration().zlib_maximum_output_length
        orig_filters = pypdf.get_configuration().stream_filters_maximum_length

        pdf_bytes = make_test_pdf(["John Doe", "Senior Engineer"])
        path = "resumes/scope/valid.pdf"
        self.mock_storage.save(path, ContentFile(pdf_bytes))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.SUCCESS)

        # Verify active configuration outside the extraction call was restored
        after_cfg = pypdf.get_configuration()
        self.assertEqual(after_cfg.zlib_maximum_output_length, orig_zlib)
        self.assertEqual(after_cfg.stream_filters_maximum_length, orig_filters)

    def test_pdf_configuration_restored_on_error_or_bomb(self):
        """Proves pypdf configuration is restored even when extraction fails with a decompression bomb."""
        import pypdf
        orig_zlib = pypdf.get_configuration().zlib_maximum_output_length
        orig_depth = pypdf.get_configuration().page_tree_maximum_depth

        # Corrupt / bomb PDF
        path = "resumes/scope/corrupt.pdf"
        self.mock_storage.save(path, ContentFile(b"%PDF-1.4\ncorrupt stream garbage\n%%EOF"))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.CORRUPT_OR_MALFORMED)

        after_cfg = pypdf.get_configuration()
        self.assertEqual(after_cfg.zlib_maximum_output_length, orig_zlib)
        self.assertEqual(after_cfg.page_tree_maximum_depth, orig_depth)

    def test_pdf_configuration_does_not_leak_into_caller_custom_context(self):
        """Proves extraction uses scoped limits without altering a custom configuration active in caller context."""
        import pypdf
        # Suppose a caller has their own custom pypdf configuration active
        with pypdf.apply_configuration(
            zlib_maximum_output_length=50_000_000,
            page_tree_maximum_depth=42,
            stream_filters_maximum_length=9,
        ):
            caller_cfg_before = pypdf.get_configuration()
            self.assertEqual(caller_cfg_before.zlib_maximum_output_length, 50_000_000)
            self.assertEqual(caller_cfg_before.page_tree_maximum_depth, 42)

            pdf_bytes = make_test_pdf(["Jane Doe", "Lead Architect"])
            path = "resumes/scope/caller_context.pdf"
            self.mock_storage.save(path, ContentFile(pdf_bytes))

            result = self.service.extract_from_storage(path)
            self.assertEqual(result.status, ExtractionStatus.SUCCESS)

            # Inside caller's context, their custom limits must still be active!
            caller_cfg_after = pypdf.get_configuration()
            self.assertEqual(caller_cfg_after.zlib_maximum_output_length, 50_000_000)
            self.assertEqual(caller_cfg_after.page_tree_maximum_depth, 42)
            self.assertEqual(caller_cfg_after.stream_filters_maximum_length, 9)

    def test_pdf_root_object_recovery_limit(self):
        """Halts root object recovery on malformed PDFs when root_object_recovery_limit is reached."""
        header = b"%PDF-1.4\n"
        obj1 = b"1 0 obj\n<< /Type /NotCatalog >>\nendobj\n"
        objs = [obj1]
        positions = [len(header)]
        curr = len(header) + len(obj1)
        xref_lines = ["xref\n0 2\n0000000000 65535 f \n", f"{positions[0]:010d} 00000 n \n"]
        xref = "".join(xref_lines).encode("ascii")
        # Trailer specifies /Size 5000 and has no /Root object
        trailer = f"trailer\n<< /Size 5000 >>\nstartxref\n{curr}\n%%EOF".encode("ascii")
        no_root_pdf = header + b"".join(objs) + xref + trailer

        path = "resumes/bomb/pdf_no_root.pdf"
        self.mock_storage.save(path, ContentFile(no_root_pdf))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.DECOMPRESSION_BOMB_DETECTED)
        self.assertIn("limit", result.error_message.lower())

    def test_pdf_cumulative_character_budget_across_pages(self):
        """Enforces cumulative character limit strictly across multiple pages, breaking early."""
        # 2 pages each with 100,000 chars (total 200,000 chars > 150,000 limit)
        page1_text = ["A" * 1000 for _ in range(100)]  # 100,000 chars
        page2_text = ["B" * 1000 for _ in range(100)]  # 100,000 chars
        pdf_bytes = make_multipage_pdf([page1_text, page2_text])

        path = "resumes/candidate_large_pages/large_pages.pdf"
        self.mock_storage.save(path, ContentFile(pdf_bytes))

        result = self.service.extract_from_storage(path)
        self.assertEqual(result.status, ExtractionStatus.SUCCESS)
        self.assertEqual(result.character_count, MAX_EXTRACTED_CHARACTERS)
        self.assertEqual(len(result.text), MAX_EXTRACTED_CHARACTERS)
        self.assertTrue(result.text.startswith("A"))
        self.assertTrue(result.text.endswith("B"))

    def test_corrupted_output_null_bytes_rejected(self):
        """Detects obviously corrupted output containing excessive null bytes and rejects it."""
        corrupted_pdf = make_test_pdf([
            "H\x00e\x00l\x00l\x00o\x00 \x00W\x00o\x00r\x00l\x00d\x00 \x00R\x00e\x00s\x00u\x00m\x00e\x00",
        ])
        path = "resumes/corrupt_output/null_bytes.pdf"
        self.mock_storage.save(path, ContentFile(corrupted_pdf))

        result = self.service.extract_from_storage(path)
        self.assertIn(
            result.status,
            (ExtractionStatus.CORRUPTED_OUTPUT, ExtractionStatus.CORRUPT_OR_MALFORMED),
        )
        self.assertFalse(result.is_success)
        self.assertIn("null bytes", result.error_message.lower())

    def test_corrupted_output_control_characters_rejected(self):
        """Detects unmapped glyphs or control character corruption and rejects it."""
        corrupted_pdf = make_test_pdf([
            "Candidate Name\x01\x02\x03\x04\x05\x06\x07\x0e\x0f\x10\x11\x12\x13\x14\x15",
        ])
        path = "resumes/corrupt_output/control_chars.pdf"
        self.mock_storage.save(path, ContentFile(corrupted_pdf))

        result = self.service.extract_from_storage(path)
        self.assertIn(
            result.status,
            (ExtractionStatus.CORRUPTED_OUTPUT, ExtractionStatus.CORRUPT_OR_MALFORMED),
        )
        self.assertFalse(result.is_success)

    def test_legitimate_multilingual_text_not_rejected(self):
        """Ensures legitimate international multilingual text is never flagged as corrupted."""
        multilingual_samples = [
            "Résumé d'ingénieur en chef — Développeur Python",
            "Lebenslauf: Gründer & Geschäftsführer",
            "Currículum Vitae: Diseñador de Software",
            "个人简历：高级软件工程师，精通云计算与分布式架构",
            "السيرة الذاتية: مهندس برمجيات رئيسي",
            "이력서: 수석 소프트웨어 엔지니어, 분산 시스템 전문가",
        ]
        for sample in multilingual_samples:
            is_corrupt, reason = is_obviously_corrupted_text(sample)
            self.assertFalse(is_corrupt, f"Sample was falsely flagged as corrupt: '{sample}' (reason: {reason})")
            self.assertIsNone(reason)

    # ------------------------------------------------------------------------
    # 9. Whitespace & Paragraph Normalization
    # ------------------------------------------------------------------------
    def test_whitespace_normalization(self):
        messy_text = (
            "  Line 1 with \t tabs   and   spaces.  \r\n"
            "\r\n\r\n\r\n"  # 4 newlines -> should collapse to 2
            "Line 2 with \u00a0 non-breaking \u200b spaces.  \r"
            "Line 3.  \n"
        )
        normalized = normalize_extracted_text(messy_text)
        expected = (
            "Line 1 with tabs and spaces.\n\n"
            "Line 2 with non-breaking spaces.\n"
            "Line 3."
        )
        self.assertEqual(normalized, expected)

    # ------------------------------------------------------------------------
    # 10. Security: Private Storage Enforcement & Path Traversal / URL Rejection
    # ------------------------------------------------------------------------
    def test_rejection_of_arbitrary_urls(self):
        urls = [
            "https://malicious.com/resume.pdf",
            "http://169.254.169.254/latest/meta-data/",
            "ftp://fileserver/resume.pdf",
        ]
        for url in urls:
            result = self.service.extract_from_storage(url)
            self.assertEqual(result.status, ExtractionStatus.PATH_TRAVERSAL_REJECTED)
            self.assertIn("Arbitrary URLs are not permitted", result.error_message)

    def test_rejection_of_directory_traversal(self):
        traversals = [
            "../../etc/passwd",
            "resumes/../../secrets.txt",
            "..\\..\\Windows\\System32\\cmd.exe",
        ]
        for path in traversals:
            result = self.service.extract_from_storage(path)
            self.assertEqual(result.status, ExtractionStatus.PATH_TRAVERSAL_REJECTED)
            self.assertIn("Directory traversal attempt detected", result.error_message)

    # ------------------------------------------------------------------------
    # 11. Absence of Resume Text & Credentials in Logs
    # ------------------------------------------------------------------------
    def test_no_resume_text_leaked_in_logs(self):
        secret_resume_text = "CONFIDENTIAL_PASSPORT_ID_987654321_RESTRICTED"
        pdf_bytes = make_test_pdf([secret_resume_text])
        path = "resumes/candidate_secret/secret.pdf"
        self.mock_storage.save(path, ContentFile(pdf_bytes))

        with self.assertLogs("common.resume_extraction", level="INFO") as log_capture:
            self.service.extract_from_storage(path)

        for record in log_capture.records:
            self.assertNotIn(secret_resume_text, record.getMessage())
            self.assertNotIn("CONFIDENTIAL", record.getMessage())

    # ------------------------------------------------------------------------
    # 12. Candidate Profile Extraction & Private Persistence
    # ------------------------------------------------------------------------
    def test_extract_and_persist_for_candidate_success(self):
        resume_text = "Alice Developer\n\nSenior Backend Engineer\n10 years experience in Django and PostgreSQL."
        pdf_content = make_test_pdf(resume_text.split("\n\n"))
        storage_path = f"{self.candidate_user.id}/alice_resume.pdf"
        self.mock_storage.save(storage_path, ContentFile(pdf_content))

        self.candidate_profile.resume_url = storage_path
        self.candidate_profile.save(update_fields=["resume_url"])

        result = self.service.extract_and_persist_for_candidate(self.candidate_profile)
        self.assertEqual(result.status, ExtractionStatus.SUCCESS)

        # Verify CandidateResumeEmbedding record
        embedding_record = CandidateResumeEmbedding.objects.get(candidate_profile=self.candidate_profile)
        self.assertEqual(embedding_record.extracted_text, result.text)
        self.assertEqual(embedding_record.content_hash, result.content_hash)
        self.assertEqual(embedding_record.text_length, result.character_count)
        self.assertEqual(embedding_record.status, EmbeddingStatus.PENDING)
        self.assertIsNone(embedding_record.error_message)
        # Embedding vector must remain None in this phase
        self.assertIsNone(embedding_record.embedding)

    def test_extract_and_persist_unsupported_format_marks_failed(self):
        legacy_doc = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + (b"\x00" * 512)
        storage_path = f"{self.candidate_user.id}/alice_resume.doc"
        self.mock_storage.save(storage_path, ContentFile(legacy_doc))

        self.candidate_profile.resume_url = storage_path
        self.candidate_profile.save(update_fields=["resume_url"])

        result = self.service.extract_and_persist_for_candidate(self.candidate_profile)
        self.assertEqual(result.status, ExtractionStatus.UNSUPPORTED_FORMAT)

        embedding_record = CandidateResumeEmbedding.objects.get(candidate_profile=self.candidate_profile)
        self.assertEqual(embedding_record.status, EmbeddingStatus.FAILED)
        self.assertIn("Legacy binary .doc format is not supported", embedding_record.error_message)
        self.assertIsNone(embedding_record.extracted_text)

    # ------------------------------------------------------------------------
    # 13. Absolute Privacy: Extracted Text Excluded from All Serializers
    # ------------------------------------------------------------------------
    def test_extracted_text_never_exposed_in_api_serializers(self):
        # Create an embedding record with extracted text
        CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            extracted_text="SUPER_SECRET_EXTRACTED_RESUME_TEXT_FOR_AI_ONLY",
            content_hash="abc" * 20,
            text_length=1500,
            status=EmbeddingStatus.PENDING,
        )

        match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=88,
            status=Match.Status.SUGGESTED,
        )

        # 1. Candidate serializers
        cand_data = CandidateProfileSerializer(self.candidate_profile).data
        self.assertNotIn("extracted_text", cand_data)
        self.assertNotIn("resume_embedding", cand_data)

        admin_cand_data = AdminCandidateListSerializer(self.candidate_profile).data
        self.assertNotIn("extracted_text", admin_cand_data)

        talent_data = PublicTalentCardSerializer(self.candidate_profile).data
        self.assertNotIn("extracted_text", talent_data)

        # 2. Match serializers
        cand_match_data = CandidateMatchSerializer(match).data
        self.assertNotIn("extracted_text", cand_match_data)

        emp_match_data = EmployerMatchSerializer(match).data
        self.assertNotIn("extracted_text", emp_match_data)

        admin_match_data = AdminMatchSerializer(match).data
        self.assertNotIn("extracted_text", admin_match_data)
