"""
Minimal valid PDF generator using stdlib only (no reportlab).

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Purpose: generate small but spec-compliant PDF 1.4 documents for the RAG verification
bundle. Each PDF contains a title + 1-2 paragraphs of Spanish text describing the
document content. Used for data/verification/rag/binaries/*.pdf.

Approach:
  - Hand-crafted PDF byte structure (cross-reference table + trailer).
  - No external dependencies beyond stdlib.
  - Produces ~400-600 byte PDF files parseable by pypdf.
  - Helper function returns raw bytes so callers can compute SHA-256.

Dependencies:
  - None (stdlib only: hashlib imported by callers, not here).

NOTE: this module is SEED-ONLY. Do NOT import it from production application code.
The PDFs it produces are minimal and not suitable for end-user display.
"""
from __future__ import annotations


def _encode_pdf_string(text: str) -> bytes:
    """Encode a Python string as a PDF literal string (parentheses-quoted, ISO-8859-1 safe).

    Purpose: produce safe PDF literal strings for Title and text runs.
    Params:
      text — the string to encode (printable ASCII/Latin-1 only).
    Returns: bytes of the PDF literal string including parentheses.
    """
    # Escape parentheses and backslash inside PDF strings.
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"({escaped})".encode("latin-1", errors="replace")


def build_minimal_pdf(title: str, body: str) -> bytes:
    """Build a minimal PDF 1.4 document with a title and body paragraph.

    Purpose: produce a valid, parseable PDF for RAG verification fixtures.
    The document uses a single page with basic text rendering.

    Params:
      title — document title (shown in text on page).
      body  — one paragraph of body text (Latin-1 characters supported).
    Returns: bytes of the complete PDF.
    Errors: none — always produces a valid PDF.

    PDF structure:
      1. Header: %PDF-1.4
      2. Objects 1-5: catalog, pages, page, font, content stream
      3. Cross-reference table (xref)
      4. Trailer
    """
    # Truncate to safe lengths for the minimal PDF format.
    title_safe = title[:80]
    body_safe = body[:300]

    # Build the page content stream (PDF graphics operators).
    content_stream = (
        "BT\n"
        "/F1 14 Tf\n"
        "50 750 Td\n"
        f"{_encode_pdf_string(title_safe).decode('latin-1')} Tj\n"
        "0 -30 Td\n"
        "/F1 10 Tf\n"
        f"{_encode_pdf_string(body_safe).decode('latin-1')} Tj\n"
        "ET"
    )
    stream_bytes = content_stream.encode("latin-1", errors="replace")
    stream_len = len(stream_bytes)

    # PDF object assembly — collect each object as bytes, track byte offsets.
    parts: list[bytes] = []
    offsets: list[int] = []

    header = b"%PDF-1.4\n"
    parts.append(header)
    current_offset = len(header)

    def _add_obj(obj_num: int, content: str) -> None:
        nonlocal current_offset
        obj_bytes = f"{obj_num} 0 obj\n{content}\nendobj\n".encode("latin-1")
        offsets.append(current_offset)
        parts.append(obj_bytes)
        current_offset += len(obj_bytes)

    # Object 1: catalog
    _add_obj(1, "<< /Type /Catalog /Pages 2 0 R >>")

    # Object 2: pages node
    _add_obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>")

    # Object 3: page (A4: 595x842 pts)
    _add_obj(
        3,
        (
            "<< /Type /Page /Parent 2 0 R "
            "/MediaBox [0 0 595 842] "
            "/Contents 5 0 R "
            "/Resources << /Font << /F1 4 0 R >> >> >>"
        ),
    )

    # Object 4: Helvetica font reference
    _add_obj(
        4,
        (
            "<< /Type /Font /Subtype /Type1 "
            "/BaseFont /Helvetica "
            "/Encoding /WinAnsiEncoding >>"
        ),
    )

    # Object 5: content stream
    stream_header = (
        f"<< /Length {stream_len} >>\n"
        "stream\n"
    )
    stream_footer = "\nendstream"
    offsets.append(current_offset)
    obj5_bytes = (
        f"5 0 obj\n{stream_header}".encode("latin-1")
        + stream_bytes
        + stream_footer.encode("latin-1")
        + b"\nendobj\n"
    )
    parts.append(obj5_bytes)
    current_offset += len(obj5_bytes)

    # Cross-reference table.
    xref_offset = current_offset
    xref_lines = ["xref\n", "0 6\n", "0000000000 65535 f \n"]
    for off in offsets:
        xref_lines.append(f"{off:010d} 00000 n \n")
    xref_bytes = "".join(xref_lines).encode("ascii")
    parts.append(xref_bytes)

    # Trailer.
    trailer = (
        f"trailer\n"
        f"<< /Size 6 /Root 1 0 R >>\n"
        f"startxref\n"
        f"{xref_offset}\n"
        f"%%EOF\n"
    ).encode("ascii")
    parts.append(trailer)

    return b"".join(parts)
