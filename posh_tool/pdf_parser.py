"""
Deterministic PDF Document Parser for POSH Policies, IC Notices, Annual Reports, and BRSR reports.
Zero AI, 100% Python-based document inspection using pdfplumber and pypdf.
"""

import io
import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from .config import EMAIL_REGEX, PHONE_REGEX, NOT_AVAILABLE

logger = logging.getLogger(__name__)

# Fallback imports
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False


class PDFDocumentParser:
    def __init__(self):
        pass

    def parse_pdf(self, pdf_bytes: bytes, filename_hint: str = "") -> Dict[str, Any]:
        """
        Reads ALL pages of the PDF document and extracts IC / POSH details verbatim.
        """
        result: Dict[str, Any] = {
            "ic_found": False,
            "presiding_officer": NOT_AVAILABLE,
            "ic_members": [],
            "ic_email": NOT_AVAILABLE,
            "ic_phone": NOT_AVAILABLE,
            "where_found": NOT_AVAILABLE,
            "date_found": NOT_AVAILABLE,
            "pages_count": 0,
            "is_scanned": False,
            "all_text_snippets": []
        }

        if not pdf_bytes:
            return result

        pages_text: List[Tuple[int, str]] = []

        # Attempt 1: pdfplumber (superior layout and table support)
        if HAS_PDFPLUMBER:
            try:
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    result["pages_count"] = len(pdf.pages)
                    for i, page in enumerate(pdf.pages, start=1):
                        txt = page.extract_text() or ""
                        # Also extract tables if present
                        tables = page.extract_tables()
                        if tables:
                            for tbl in tables:
                                for row in tbl:
                                    row_filtered = [str(c).strip() for c in row if c]
                                    txt += "\n" + " | ".join(row_filtered)
                        pages_text.append((i, txt))
            except Exception as e:
                logger.debug(f"pdfplumber failed: {e}")

        # Attempt 2: pypdf if pdfplumber didn't extract or failed
        if (not pages_text or sum(len(t) for _, t in pages_text) < 50) and HAS_PYPDF:
            pages_text = []
            try:
                reader = PdfReader(io.BytesIO(pdf_bytes))
                result["pages_count"] = len(reader.pages)
                for i, page in enumerate(reader.pages, start=1):
                    txt = page.extract_text() or ""
                    pages_text.append((i, txt))
            except Exception as e:
                logger.debug(f"pypdf failed: {e}")

        if not pages_text:
            result["is_scanned"] = True
            return result

        total_extracted_chars = sum(len(t) for _, t in pages_text)
        if total_extracted_chars < 50 and result["pages_count"] > 0:
            result["is_scanned"] = True
            return result

        # Check for document publication dates
        date_pattern = re.compile(
            r'\b(?:date|effective|approved|adopted|version|revised|year)[\s:\-–—]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[A-Za-z]+[\s,]+[0-9]{4}|[0-9]{4})\b',
            re.IGNORECASE
        )
        for _, text in pages_text:
            m = date_pattern.search(text)
            if m:
                result["date_found"] = m.group(1).strip()
                break

        # Priority IC search targets
        ic_clues = [
            "presiding officer",
            "internal committee",
            "internal complaints committee",
            "icc member",
            "members of the internal committee",
            "external member",
            "complaints may be sent to",
            "redressal committee",
            "posh committee"
        ]

        found_members = []
        found_po = None
        found_ic_email = None
        found_ic_phone = None
        found_section_desc = None

        # Inspect all pages, with special attention to Annexures, Appendices, and Contact sections
        for page_num, text in pages_text:
            text_lower = text.lower()
            if not any(clue in text_lower for clue in ic_clues):
                continue

            result["ic_found"] = True

            # Determine section context
            section_label = f"Page {page_num}"
            if "annexure" in text_lower:
                m_ann = re.search(r'(annexure\s+[a-z0-9\-]+)', text, re.IGNORECASE)
                if m_ann:
                    section_label += f", {m_ann.group(1).title()}"
                else:
                    section_label += ", Annexure"
            elif "appendix" in text_lower:
                section_label += ", Appendix"
            elif "schedule" in text_lower:
                section_label += ", Schedule"
            elif "composition" in text_lower:
                section_label += ", Composition of IC"
            elif "contact" in text_lower:
                section_label += ", Contact Details"

            if not found_section_desc:
                doc_name = filename_hint or "POSH Document"
                found_section_desc = f"{doc_name}, {section_label}"

            # Extract Emails on this page
            emails = EMAIL_REGEX.findall(text)
            for em in emails:
                em_lower = em.lower()
                # Prioritize posh / ic / grievance / ethics emails
                if any(k in em_lower for k in ["posh", "ic", "icc", "complaint", "grievance", "redressal", "harassment", "ethics", "ombuds"]):
                    if not found_ic_email:
                        found_ic_email = em
                elif not found_ic_email and not any(k in em_lower for k in ["sales", "info", "support", "careers", "press"]):
                    found_ic_email = em

            # Extract Phones on this page
            phones = PHONE_REGEX.findall(text)
            for ph in phones:
                cleaned_ph = re.sub(r'[\s\-]', '', ph)
                if len(cleaned_ph) >= 10:
                    if not found_ic_phone:
                        found_ic_phone = ph.strip()

            # Look for Presiding Officer (as published, including honorific if present)
            po_match = re.search(
                r'presiding\s+officer[\s:\-–—]+((?:(?:Ms\.|Mrs\.|Dr\.|Mr\.|Adv\.)\s+)?[A-Z][A-Za-z\.\s]{2,30}?)(?:\n|,|\(|\-|\bat\b|\bemail\b|$)',
                text,
                re.IGNORECASE
            )
            if po_match and not found_po:
                found_po = po_match.group(1).strip()

            # Look for External Member
            ext_match = re.search(
                r'external\s+member[\s:\-–—]+((?:(?:Ms\.|Mrs\.|Dr\.|Mr\.|Adv\.)\s+)?[A-Z][A-Za-z\.\s]{2,30}?)(?:\n|,|\(|\-|\bat\b|\bemail\b|$)',
                text,
                re.IGNORECASE
            )
            if ext_match:
                ext_name = f"{ext_match.group(1).strip()} (External Member)"
                if ext_name not in found_members:
                    found_members.append(ext_name)

            # Look for general member lines
            lines = text.splitlines()
            for line in lines:
                l_str = line.strip()
                if re.match(r'^(?:[0-9]{1,2}[\.\)]\s*)?(?:Ms\.|Mrs\.|Dr\.|Mr\.)\s+[A-Za-z\s]{3,30}\s*[-–—|]\s*(?:Member|Presiding Officer)', l_str, re.IGNORECASE):
                    if l_str not in found_members:
                        found_members.append(l_str)

        if found_po:
            result["presiding_officer"] = found_po
            if found_po not in found_members:
                found_members.insert(0, f"{found_po} (Presiding Officer)")

        if found_members:
            result["ic_members"] = found_members
        if found_ic_email:
            result["ic_email"] = found_ic_email
        if found_ic_phone:
            result["ic_phone"] = found_ic_phone
        if found_section_desc:
            result["where_found"] = found_section_desc

        return result

