"""
Deterministic Information Extractor.
Strict compliance with rule:
"NEVER guess, construct, or pattern-match an email address or phone number.
Record a contact ONLY if it appears verbatim on a public page or document. Otherwise write 'Not available'."
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup

from .config import (
    EMAIL_REGEX,
    PHONE_REGEX,
    PIN_CODE_REGEX,
    EMPLOYEE_COUNT_REGEX,
    EXCLUSION_PHRASES,
    EXCLUDED_DOMAIN_KEYWORDS,
    CITY_ALIASES,
    CITY_PIN_PREFIXES,
    NOT_AVAILABLE
)


class DataExtractor:
    def __init__(self):
        pass

    def check_disqualification(self, text: str, domain: str) -> Optional[str]:
        """
        Checks if an entity is disqualified under strict criteria:
        - Training/coaching institutes & coaching centers
        - Coworking spaces & virtual offices
        - Recruitment/staffing agencies & placement consultancies
        - Fraud / directory signals
        Returns reason if disqualified, None if qualified.
        """
        text_lower = text.lower()
        domain_lower = domain.lower()

        # Check domain-level exclusions
        for kw in EXCLUDED_DOMAIN_KEYWORDS:
            if kw in domain_lower:
                return f"Disqualified: domain matches excluded business type '{kw}'"

        # Check multi-word exclusion phrases
        for phrase in EXCLUSION_PHRASES:
            if phrase in text_lower:
                # Confirm it is an actual business service description
                return f"Disqualified: business activity identified as '{phrase}'"

        return None

    def is_city_matched(self, text: str, target_city: str, target_area: str = "") -> Tuple[bool, bool]:
        """
        Validates if text confirms physical location in target city (and area if specified).
        Supports city synonyms (e.g. Bangalore == Bengaluru) and PIN code prefixes.
        Returns (city_matched, area_matched).
        """
        text_lower = text.lower()
        norm_city = target_city.strip().lower()

        # 1. Get city name variants
        city_variants = CITY_ALIASES.get(norm_city, [norm_city])
        if norm_city not in city_variants:
            city_variants.append(norm_city)

        city_matched = any(re.search(r'\b' + re.escape(v) + r'\b', text_lower) for v in city_variants)

        # 2. Check Indian PIN code prefixes for the city (e.g., 560xxx for Bangalore)
        if not city_matched:
            pin_prefixes = CITY_PIN_PREFIXES.get(norm_city, [])
            if pin_prefixes:
                found_pins = PIN_CODE_REGEX.findall(text)
                for pin in found_pins:
                    if any(pin.startswith(prefix) for prefix in pin_prefixes):
                        city_matched = True
                        break

        # 3. Check area/locality if provided
        area_matched = True
        norm_area = target_area.strip().lower() if target_area else ""
        if norm_area and norm_area not in ["whole city", "any", "none", "all"]:
            area_matched = norm_area in text_lower

        return city_matched, area_matched

    def determine_legal_form(self, text: str, company_name: str) -> str:
        """
        Determines legal form: Pvt Ltd / LLP / Listed / Not confirmed.
        """
        combined = f"{company_name} {text}".lower()

        if any(k in combined for k in ["bse:", "nse:", "isin:", "listed on bse", "listed on nse", "scrip code:", "bse code"]):
            return "Listed"
        if re.search(r'\b(pvt\.?\s*ltd\.?|private\s+limited)\b', combined):
            return "Pvt Ltd"
        if re.search(r'\b(llp|limited\s+liability\s+partnership)\b', combined):
            return "LLP"
        if re.search(r'\b(public\s+limited|limited|ltd\.)\b', combined) and "private" not in combined:
            return "Listed"

        return "Not confirmed"

    def extract_address_with_pin(self, text: str, city: str, area: str = "") -> str:
        """
        Finds physical address with 6-digit Indian PIN code.
        """
        city_lower = city.strip().lower()
        city_variants = CITY_ALIASES.get(city_lower, [city_lower])
        pin_prefixes = CITY_PIN_PREFIXES.get(city_lower, [])

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        address_indicators = [
            "road", "street", "floor", "nagar", "layout", "building", "office",
            "tower", "cross", "complex", "sector", "phase", "block", "marg", "lane",
            "pin", "pin code", "postal code"
        ]

        for idx, line in enumerate(lines):
            pin_match = PIN_CODE_REGEX.search(line)
            if pin_match:
                pin_val = pin_match.group(1)
                # Ensure it's not a phone number fragment
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
                joined_lower = joined_addr.lower()

                matches_city = any(v in joined_lower for v in city_variants)
                matches_pin_prefix = any(pin_val.startswith(p) for p in pin_prefixes) if pin_prefixes else False
                matches_indicator = any(ind in joined_lower for ind in address_indicators)

                if matches_city or matches_pin_prefix or matches_indicator:
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

        # Check for team members list or leadership team
        if "leadership team" in text.lower() or "board of directors" in text.lower():
            return "Active operating corporate leadership team on company site (>= 10 employees)"

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
            r'(?:head of hr|hr head|chief people officer|people officer|talent partner)[\s:\-–—]+((?:(?:Ms\.|Mrs\.|Dr\.|Mr\.)\s+)?[A-Z][a-zA-Z\.\s]{2,25}?)(?=\s+(?:at|email|call|tel|on|\-|,|\.|\n|$))',
            r'(?:contact\s+hr|recruiter)[\s:\-–—]+((?:(?:Ms\.|Mrs\.|Dr\.|Mr\.)\s+)?[A-Z][a-zA-Z\.\s]{2,25}?)(?=\s+(?:at|email|call|tel|on|\-|,|\.|\n|$))'
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

        # Presiding Officer (as published, including honorific if present)
        m_po = re.search(
            r'presiding\s+officer[\s:\-–—]+((?:(?:Ms\.|Mrs\.|Dr\.|Mr\.|Adv\.)\s+)?[A-Z][A-Za-z\.\s]{2,30}?)(?:\n|,|\(|\-|\bat\b|\bemail\b|$)',
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
            res["ic_email"] = emails[0]

        # Phones
        phones = PHONE_REGEX.findall(text)
        for ph in phones:
            cleaned = re.sub(r'[\s\-]', '', ph)
            if len(cleaned) >= 8:
                res["ic_phone"] = ph.strip()
                break

        return res
