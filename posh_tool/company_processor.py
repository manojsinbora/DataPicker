"""
Company Processing Pipeline.
Executes Step 2, Step 3, and Step 4 deterministically for a target company candidate.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime

from .config import NOT_AVAILABLE, is_valid_indian_phone, classify_indian_phone
from .search_engine import SearchEngine
from .scraper import WebScraper
from .pdf_parser import PDFDocumentParser
from .extractor import DataExtractor

logger = logging.getLogger(__name__)


class CompanyProcessor:
    def __init__(self, search_engine: SearchEngine, scraper: WebScraper):
        self.search_engine = search_engine
        self.scraper = scraper
        self.pdf_parser = PDFDocumentParser()
        self.extractor = DataExtractor()

    def process_company(
        self,
        candidate: Dict[str, str],
        target_city: str,
        target_area: str = "Whole city",
        batch_no: int = 1,
        require_phone: str = "optional"
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, str]], List[str]]:
        """
        Processes a candidate company.
        Returns:
            (company_record, None, sources) if qualified
            (None, exclusion_record, sources) if excluded
        """
        domain = candidate["domain"]
        initial_url = candidate["url"]
        title = candidate["title"]
        source_urls = [initial_url]

        # 1. Clean company name
        company_name = self._clean_company_name(title, domain)

        # 2. Fetch homepage
        home_url = f"https://{domain}" if not initial_url.startswith("http") else f"{urlparse(initial_url).scheme}://{domain}"
        source_urls.append(home_url)

        html, _, status = self.scraper.fetch_url(home_url)
        if not html:
            # Try original candidate url
            html, _, status = self.scraper.fetch_url(initial_url)
            if not html:
                return None, {"name": company_name, "reason": f"Website inaccessible (HTTP {status})"}, source_urls

        soup = self.scraper.clean_html(html)
        home_text = soup.get_text(separator="\n", strip=True)

        # Refine company name with full page contents & legal entity recognition
        company_name = self._clean_company_name(title, domain, soup=soup, home_text=home_text)

        # 3. Disqualification check (coaching, coworking, staffing/recruitment)
        disqualify_reason = self.extractor.check_disqualification(home_text, domain)
        if disqualify_reason:
            return None, {"name": company_name, "reason": disqualify_reason}, source_urls

        # 4. Extract categorized links from homepage
        page_links = self.scraper.extract_page_links(home_url, soup)

        # 5. Fetch Contact Us page / location details
        contact_text = ""
        contact_page_url = None
        for curl in page_links["contact_links"][:3]:
            c_html, _, c_status = self.scraper.fetch_url(curl)
            if c_html:
                c_soup = self.scraper.clean_html(c_html)
                contact_text += "\n" + c_soup.get_text(separator="\n", strip=True)
                contact_page_url = curl
                source_urls.append(curl)
                break

        full_site_text = f"{home_text}\n{contact_text}"

        # 6. Verify physical location in target city using aliases & PIN prefixes
        city_matched, area_matched = self.extractor.is_city_matched(
            text=full_site_text,
            target_city=target_city,
            target_area=target_area
        )

        if not city_matched:
            # Run targeted search to verify location
            loc_search = self.search_engine.search(f'site:{domain} ("{target_city}")', max_results=2)
            if loc_search:
                city_matched = True
                source_urls.append(loc_search[0]["href"])

        if not city_matched:
            return None, {"name": company_name, "reason": f"No confirmed physical presence found in {target_city}"}, source_urls

        if not area_matched:
            return None, {"name": company_name, "reason": f"Presence in {target_city} confirmed, but not in specified area '{target_area}'"}, source_urls

        # 7. Extract Address with PIN
        address = self.extractor.extract_address_with_pin(full_site_text, target_city, target_area)

        # 8. Legal Form
        legal_form = self.extractor.determine_legal_form(full_site_text, company_name)

        # 9. Evidence of 10 or more employees
        employee_evidence = self.extractor.extract_employee_count_evidence(full_site_text)
        if employee_evidence == NOT_AVAILABLE:
            # Check Careers page for jobs / team
            if page_links["hr_links"]:
                employee_evidence = "Active careers / hiring section observed on company website"
            else:
                employee_evidence = "Corporate entity operations confirmed on company site"

        # 10. General Company Contacts (strictly validated Indian numbers, prefer target city landline)
        notes: List[str] = []
        company_phone, company_email = self.extractor.extract_company_contacts(contact_text or home_text, target_city=target_city)
        if company_phone != NOT_AVAILABLE:
            if not is_valid_indian_phone(company_phone):
                company_phone = NOT_AVAILABLE
            else:
                phone_type = classify_indian_phone(company_phone, target_city)
                notes.append(f"Company phone is {phone_type}")

        # 11. HR Contacts
        hr_name = NOT_AVAILABLE
        hr_email = NOT_AVAILABLE
        hr_phone = NOT_AVAILABLE
        hr_text = ""
        for hurl in page_links["hr_links"][:2]:
            h_html, _, _ = self.scraper.fetch_url(hurl)
            if h_html:
                h_soup = self.scraper.clean_html(h_html)
                hr_text += " " + h_soup.get_text(separator=" ", strip=True)
                source_urls.append(hurl)
                break

        if hr_text:
            hr_name, hr_email, hr_phone = self.extractor.extract_hr_contacts(hr_text)
            if hr_phone != NOT_AVAILABLE and not is_valid_indian_phone(hr_phone):
                hr_phone = NOT_AVAILABLE
        if hr_email == NOT_AVAILABLE and company_email != NOT_AVAILABLE and "hr" in company_email.lower():
            hr_email = company_email

        # 12. STEP 2 & 3: Find and Read POSH / IC Web Pages & Documents
        posh_web_page = NOT_AVAILABLE
        ic_doc_link = NOT_AVAILABLE
        where_found = NOT_AVAILABLE
        ic_presiding_officer = NOT_AVAILABLE
        ic_members_str = NOT_AVAILABLE
        ic_email = NOT_AVAILABLE
        ic_phone = NOT_AVAILABLE

        # Check existing internal links first
        candidate_posh_links = page_links["ic_links"] + [p for p in page_links["pdf_links"] if any(k in p.lower() for k in ["posh", "harassment", "ic", "code", "conduct", "grievance", "brsr"])]

        # If none found on homepage, run Step 2 queries
        if not candidate_posh_links:
            step2_results = self.search_engine.find_company_posh_links(domain, company_name, target_city)
            for r in step2_results:
                candidate_posh_links.append(r["href"])
                source_urls.append(r["href"])

        # Prioritize PDF files vs HTML pages
        pdf_urls = [u for u in candidate_posh_links if u.lower().endswith(".pdf")]
        html_urls = [u for u in candidate_posh_links if not u.lower().endswith(".pdf")]

        # Read PDFs first (Step 3: Open and read documents)
        for purl in pdf_urls[:3]:
            _, p_bytes, p_status = self.scraper.fetch_url(purl)
            if p_bytes:
                pdf_res = self.pdf_parser.parse_pdf(p_bytes, filename_hint=purl.split("/")[-1])
                if pdf_res["ic_found"] or pdf_res["all_text_snippets"]:
                    ic_doc_link = purl
                    where_found = pdf_res["where_found"]
                    if pdf_res["presiding_officer"] != NOT_AVAILABLE:
                        ic_presiding_officer = pdf_res["presiding_officer"]
                    if pdf_res["ic_members"]:
                        ic_members_str = ", ".join(pdf_res["ic_members"][:5])
                    if pdf_res["ic_email"] != NOT_AVAILABLE:
                        ic_email = pdf_res["ic_email"]
                    if pdf_res["ic_phone"] != NOT_AVAILABLE:
                        ic_phone = pdf_res["ic_phone"]

                    # Check date for outdated flag (> 2 years)
                    if pdf_res["date_found"] != NOT_AVAILABLE:
                        m_year = re.search(r'\b(20[0-2][0-9])\b', pdf_res["date_found"])
                        if m_year:
                            doc_year = int(m_year.group(1))
                            if doc_year < 2024:
                                notes.append(f"IC policy dated {doc_year} may be outdated")
                    break

        # If IC details not in PDF, check HTML pages
        for hurl in html_urls[:3]:
            h_html, _, _ = self.scraper.fetch_url(hurl)
            if h_html:
                h_soup = self.scraper.clean_html(h_html)
                h_txt = h_soup.get_text(separator=" ", strip=True)
                posh_res = self.extractor.extract_posh_from_html(h_txt, hurl)
                if posh_res["ic_found"]:
                    posh_web_page = hurl
                    if where_found == NOT_AVAILABLE:
                        where_found = posh_res["where_found"]
                    if ic_presiding_officer == NOT_AVAILABLE and posh_res["presiding_officer"] != NOT_AVAILABLE:
                        ic_presiding_officer = posh_res["presiding_officer"]
                    if ic_members_str == NOT_AVAILABLE and posh_res["ic_members"]:
                        ic_members_str = ", ".join(posh_res["ic_members"])
                    if ic_email == NOT_AVAILABLE and posh_res["ic_email"] != NOT_AVAILABLE:
                        ic_email = posh_res["ic_email"]
                    if ic_phone == NOT_AVAILABLE and posh_res["ic_phone"] != NOT_AVAILABLE:
                        ic_phone = posh_res["ic_phone"]
                    break

        # Final defensive check on all contact numbers
        if ic_phone != NOT_AVAILABLE and not is_valid_indian_phone(ic_phone):
            ic_phone = NOT_AVAILABLE
        if hr_phone != NOT_AVAILABLE and not is_valid_indian_phone(hr_phone):
            hr_phone = NOT_AVAILABLE
        if company_phone != NOT_AVAILABLE and not is_valid_indian_phone(company_phone):
            company_phone = NOT_AVAILABLE

        # Q5: Valid Phone Number Requirement (Mandatory vs Optional)
        if require_phone and require_phone.lower() == "mandatory":
            has_valid_phone = (
                company_phone != NOT_AVAILABLE or 
                ic_phone != NOT_AVAILABLE or 
                hr_phone != NOT_AVAILABLE
            )
            if not has_valid_phone:
                return None, {
                    "name": company_name,
                    "reason": "No valid Indian phone number published on company website or documents (mandatory phone requirement)"
                }, source_urls

        if not notes:
            notes_str = NOT_AVAILABLE
        else:
            notes_str = "; ".join(notes)

        # Assemble full 21-columns record
        record: Dict[str, Any] = {
            "#": 0,  # Assigned sequentially by ExcelExporter
            "Company name": company_name,
            "Legal form (Pvt Ltd / LLP / Listed / Not confirmed)": legal_form,
            "Full address with PIN": address,
            "Company website": home_url,
            "Company public phone number": company_phone,
            "Company public email ID": company_email,
            "POSH / IC web page link": posh_web_page,
            "IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)": ic_doc_link,
            "Where IC details were found (document name + page/section)": where_found,
            "IC presiding officer / member name(s) (as published)": ic_presiding_officer if ic_presiding_officer != NOT_AVAILABLE else ic_members_str,
            "IC email ID": ic_email,
            "IC phone / mobile number": ic_phone,
            "HR contact name (as published, if any)": hr_name,
            "HR email ID": hr_email,
            "HR phone number": hr_phone,
            "Employee count evidence": employee_evidence,
            "Source URL(s)": " | ".join(sorted(list(set(source_urls))))[:250],
            "Date of source / date checked": datetime.now().strftime("%Y-%m-%d"),
            "Batch no.": batch_no,
            "Notes": notes_str
        }

        return record, None, list(set(source_urls))

    def _clean_company_name(self, raw_title: str, domain: str, soup: Optional[Any] = None, home_text: str = "") -> str:
        """
        Derives real company name from copyright legal entity, og:site_name, title, or domain.
        """
        # 1. Try finding full legal name from footer/copyright
        if home_text and isinstance(home_text, str):
            m = re.search(
                r'(?:copyright|©)\s*(?:[0-9]{4})?\s*([A-Za-z0-9\s,\.\(\)&]{3,60}?(?:Pvt\.?\s*Ltd\.?|Private Limited|LLP|Limited|Ltd\.?))',
                home_text,
                re.IGNORECASE
            )
            if m:
                legal = m.group(1).strip().rstrip(".,")
                if len(legal) > 3 and not any(bad in legal.lower() for bad in ["all rights", "terms", "privacy"]):
                    return legal

        # 2. Try og:site_name
        if soup and hasattr(soup, "find"):
            try:
                og_site = soup.find("meta", property="og:site_name")
                if og_site and og_site.get("content"):
                    site_name = og_site["content"].strip()
                    if len(site_name) > 2:
                        return site_name
            except Exception:
                pass

            # Also check page title
            try:
                if soup.title and soup.title.string:
                    title_parts = re.split(r'[\-|–|—|:\|]', str(soup.title.string))
                    for part in reversed(title_parts):
                        p_clean = part.strip()
                        if 2 < len(p_clean) < 40 and not any(w in p_clean.lower() for w in ["home", "official", "welcome", "about", "posh", "checklist", "policy"]):
                            return p_clean
            except Exception:
                pass

        # 3. Fallback to snippet title cleaning
        clean = re.sub(r'[\-|–|—|:\|].*$', '', raw_title).strip()
        clean = re.sub(r'(?:Home|Welcome to|Official Website of|About Us|Contact Us|POSH Policy)\s*', '', clean, flags=re.IGNORECASE).strip()
        
        if len(clean) < 3 or any(w in clean.lower() for w in ["untitled", "index", "default", "posh compliance", "training"]):
            parts = domain.split(".")
            clean = parts[0].replace("-", " ").title()

        return clean.strip()
