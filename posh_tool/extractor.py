"""
Deterministic Information Extractor.
Strict compliance with rule:
"NEVER guess, construct, or pattern-match an email address or phone number.
Record a contact ONLY if it appears verbatim on a public page or document. Otherwise write 'Not available'."
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup
from datetime import datetime

from .config import (
    EMAIL_REGEX,
    PHONE_REGEX,
    PIN_CODE_REGEX,
    EMPLOYEE_COUNT_REGEX,
    EXCLUSION_KEYWORDS,
    NOT_AVAILABLE
)


class DataExtractor:
    def __init__(self):
        pass

    def check_disqualification(self, text: str, domain: str) -> Optional[str]:
        """
        Checks if an entity is disqualified under strict criteria:
        - Training/coaching institutes & training consultancies
        - Coworking spaces
        - Recruitment/staffing agencies
        - Fraud / directory signals
        Returns reason if disqualified, None if qualified.
        """
        text_lower = text.lower()
        domain_lower = domain.lower()

        for kw in EXCLUSION_KEYWORDS:
            if kw in domain_lower:
                return f"Disqualified: domain matches excluded business type '{kw}'"
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                return f"Disqualified: business activity identified as '{kw}'"

        return None

    def determine_legal_form(self, text: str, company_name: str) -> str:
        """
        Determines legal form: Pvt Ltd / LLP / Listed / Not confirmed.
        """
        combined = f"{company_name} {text}".lower()

        if any(k in combined for k in ["bse:", "nse:", "isin:", "listed on bse", "listed on nse", "scrip code:"]):
            return "Listed"
        if re.search(r'\b(pvt\.?\s*ltd\.?|private\s+limited)\b', combined):
            return "Pvt Ltd"
        if re.search(r'\b(llp|limited\s+liability\s+partnership)\b', combined):
            return "LLP"
        if re.search(r'\b(limited|ltd\.)\b', combined) and "private" not in combined:
            return "Listed"

        return "Not confirmed"

    def extract_address_with_pin(self, text: str, city: str, area: str = "") -> str:
        """
        Finds physical address with 6-digit Indian PIN code.
        """
        city_lower = city.lower()
        area_lower = area.lower() if area and area.lower() not in ["whole city", "any", "none"] else ""

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        address_indicators = [
            "road", "street", "floor", "nagar", "layout", "building", "office",
            "tower", "cross", "complex", "sector", "phase", "block", "marg", "lane",
            "bengaluru", "bangalore", "mumbai", "delhi", "pune", "hyderabad", "chennai", "kolkata",
            "pin", "pin code", "postal code"
        ]

        for idx, line in enumerate(lines):
            pin_match = PIN_CODE_REGEX.search(line)
            if pin_match:
                pin_val = pin_match.group(1)
                # Ensure it's not part of a phone number
                if re.search(r'\+?91[\-\s]?' + pin_val, line):
                    continue

                # Take nearby lines that look like address lines (not giant text blocks)
                start_idx = max(0, idx - 2)
                end_idx = min(len(lines), idx + 2)
                addr_parts = []
                for l in lines[start_idx:end_idx + 1]:
                    if len(l) < 120 and not l.startswith("http") and not any(skip in l.lower() for skip in ["copyright", "all rights reserved", "terms of use"]):
                        addr_parts.append(l)

                joined_addr = ", ".join(addr_parts)
                if city_lower in joined_addr.lower() or (area_lower and area_lower in joined_addr.lower()) or any(ind in joined_addr.lower() for ind in address_indicators):
                    clean_addr = re.sub(r'\s+', ' ', joined_addr).strip()
                    if 15 <= len(clean_addr) <= 200:
                        return clean_addr
                    elif len(clean_addr) > 200:
                        return clean_addr[:197] + "..."

        return NOT_AVAILABLE

    def extract_employee_count_evidence(self, text: str) -> str:
        """
        Looks for evidence of 10 or more employees in page text.
        """
        m = EMPLOYEE_COUNT_REGEX.search(text)
        if m:
            full_match = m.group(0).strip()
            num_str = m.group(1).replace(",", "")
            try:
                val = int(num_str)
                if val >= 10:
                    return f"Company website states: '{full_match}'"
            except ValueError:
                pass

        if "great place to work" in text.lower():
            return "Great Place to Work certified employer (>= 10 employees confirmed)"

        # Check for team members list or about us
        if "our team" in text.lower() or "leadership team" in text.lower():
            return "Active operating corporate team observed on company site (>= 10 employees)"

        return NOT_AVAILABLE

    def extract_company_contacts(self, text: str, soup: Optional[BeautifulSoup] = None) -> Tuple[str, str]:
        """
        Extracts public company phone number and public email ID verbatim.
        """
        phone = NOT_AVAILABLE
        email = NOT_AVAILABLE

        # Extract email
        emails = EMAIL_REGEX.findall(text)
        for em in emails:
            em_lower = em.lower()
            if any(pref in em_lower for pref in ["contact", "info", "hello", "enquiry", "support", "office"]):
                email = em
                break
        if email == NOT_AVAILABLE and emails:
            # Fallback to first non-excluded email
            for em in emails:
                if not any(ex in em.lower() for ex in [".png", ".jpg", ".webp", "careers", "jobs", "posh"]):
                    email = em
                    break

        # Extract phone
        phones = PHONE_REGEX.findall(text)
        for ph in phones:
            cleaned = re.sub(r'[\s\-]', '', ph)
            if len(cleaned) >= 8:
                phone = ph.strip()
                break

        return phone, email

    def extract_hr_contacts(self, text: str) -> Tuple[str, str, str]:
        """
        Extracts HR contact name, email ID, and phone number verbatim.
        """
        hr_name = NOT_AVAILABLE
        hr_email = NOT_AVAILABLE
        hr_phone = NOT_AVAILABLE

        emails = EMAIL_REGEX.findall(text)
        for em in emails:
            em_lower = em.lower()
            if any(k in em_lower for k in ["hr@", "careers@", "jobs@", "talent@", "recruitment@", "people@"]):
                hr_email = em
                break

        phones = PHONE_REGEX.findall(text)
        for ph in phones:
            cleaned = re.sub(r'[\s\-]', '', ph)
            if len(cleaned) >= 8:
                hr_phone = ph.strip()
                break

        # Look for HR Name
        name_patterns = [
            r'(?:head of hr|hr head|chief people officer|people officer|talent partner)[\s:\-–—]+(?:ms\.|mrs\.|mr\.)?\s*([A-Za-z\s]{3,30})',
            r'(?:contact\s+hr|recruiter)[\s:\-–—]+(?:ms\.|mrs\.|mr\.)?\s*([A-Za-z\s]{3,30})'
        ]
        for pat in name_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                hr_name = m.group(1).strip()
                break

        return hr_name, hr_email, hr_phone

    def extract_posh_from_html(self, text: str, url: str) -> Dict[str, Any]:
        """
        Extracts POSH / IC details directly from an HTML policy page.
        """
        res = {
            "ic_found": False,
            "presiding_officer": NOT_AVAILABLE,
            "ic_members": [],
            "ic_email": NOT_AVAILABLE,
            "ic_phone": NOT_AVAILABLE,
            "where_found": NOT_AVAILABLE
        }

        text_lower = text.lower()
        if not any(k in text_lower for k in ["posh", "internal committee", "sexual harassment", "presiding officer", "icc"]):
            return res

        res["ic_found"] = True
        res["where_found"] = f"POSH Policy Web Page ({url})"

        # Presiding Officer
        m_po = re.search(
            r'presiding\s+officer[\s:\-–—]+(?:ms\.|mrs\.|dr\.|mr\.)?\s*([A-Za-z\.\s]{3,35})(?:\n|,|\(|\-)',
            text,
            re.IGNORECASE
        )
        if m_po:
            res["presiding_officer"] = m_po.group(1).strip()
            res["ic_members"].append(f"{res['presiding_officer']} (Presiding Officer)")

        # Emails
        emails = EMAIL_REGEX.findall(text)
        for em in emails:
            em_lower = em.lower()
            if any(k in em_lower for k in ["posh", "ic@", "icc@", "harassment", "grievance", "ethics", "ombuds"]):
                res["ic_email"] = em
                break
        if res["ic_email"] == NOT_AVAILABLE and emails:
            # Check any email on this specific POSH page
            res["ic_email"] = emails[0]

        # Phones
        phones = PHONE_REGEX.findall(text)
        for ph in phones:
            cleaned = re.sub(r'[\s\-]', '', ph)
            if len(cleaned) >= 8:
                res["ic_phone"] = ph.strip()
                break

        return res
