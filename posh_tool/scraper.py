"""
Public Web Scraper module using primp/requests with Cloudflare de-obfuscation.
Zero AI, 100% deterministic HTML retrieval and parsing.
"""

import logging
import re
from typing import List, Dict, Optional, Tuple, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from .config import (
    DEFAULT_USER_AGENT,
    HTTP_TIMEOUT,
    IC_KEYWORDS,
    HR_KEYWORDS
)

try:
    import primp
    HAS_PRIMP = True
except ImportError:
    HAS_PRIMP = False

import requests

logger = logging.getLogger(__name__)


def decode_cloudflare_email(cf_hex: str) -> str:
    """
    Decodes Cloudflare email-protection hex strings deterministically using XOR.
    """
    try:
        k = int(cf_hex[:2], 16)
        return "".join(chr(int(cf_hex[i:i+2], 16) ^ k) for i in range(2, len(cf_hex), 2))
    except Exception:
        return ""


class WebScraper:
    def __init__(self, timeout: int = HTTP_TIMEOUT):
        self.timeout = timeout
        if HAS_PRIMP:
            try:
                self.client = primp.Client(impersonate="chrome_124", verify=False, timeout=self.timeout)
            except Exception:
                self.client = None
        else:
            self.client = None

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        })

    def fetch_url(self, url: str) -> Tuple[Optional[str], Optional[bytes], int]:
        """
        Fetches URL contents. Returns (text_content, raw_bytes, status_code).
        """
        try:
            if self.client:
                resp = self.client.get(url, timeout=self.timeout)
                status = resp.status_code
                if status == 200:
                    return resp.text, resp.content, status
            
            # Fallback to requests session
            resp = self.session.get(url, timeout=self.timeout, verify=False)
            if resp.status_code == 200:
                return resp.text, resp.content, resp.status_code
            return None, None, resp.status_code
        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return None, None, 0

    def clean_html(self, html: str) -> BeautifulSoup:
        """
        Parses HTML and replaces Cloudflare-protected email tags with plain text.
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # De-obfuscate Cloudflare protected emails
        for cf_tag in soup.find_all(attrs={"data-cfemail": True}):
            cf_hex = cf_tag.get("data-cfemail")
            if cf_hex:
                decoded = decode_cloudflare_email(cf_hex)
                if decoded:
                    cf_tag.replace_with(decoded)

        for a in soup.find_all("a", href=True):
            if "/cdn-cgi/l/email-protection#" in a["href"]:
                cf_hex = a["href"].split("/cdn-cgi/l/email-protection#")[-1]
                decoded = decode_cloudflare_email(cf_hex)
                if decoded:
                    a.replace_with(decoded)

        return soup

    def extract_page_links(self, base_url: str, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """
        Categorizes links found on a page into:
        - ic_links: POSH / IC / Complaints / Ethics / Governance links
        - hr_links: Careers / Work with us / Jobs links
        - contact_links: Contact Us / Locations / Office links
        - pdf_links: Direct PDF policy documents
        """
        base_domain = urlparse(base_url).netloc.lower()
        ic_links: Set[str] = set()
        hr_links: Set[str] = set()
        contact_links: Set[str] = set()
        pdf_links: Set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            # Check if internal domain or related subdomain
            if base_domain not in parsed.netloc.lower() and not parsed.netloc.lower().endswith("." + base_domain):
                # External link: only keep if it is a direct PDF document or official filing
                if not full_url.lower().endswith(".pdf"):
                    continue

            link_text = (a.get_text() or "").lower()
            href_lower = full_url.lower()

            if href_lower.endswith(".pdf"):
                pdf_links.add(full_url)

            # Check IC keywords
            if any(k in link_text or k in href_lower for k in IC_KEYWORDS):
                ic_links.add(full_url)

            # Check HR keywords
            if any(k in link_text or k in href_lower for k in HR_KEYWORDS):
                hr_links.add(full_url)

            # Check Contact keywords
            if any(k in link_text or k in href_lower for k in ["contact", "reach-us", "get-in-touch", "locations", "offices", "branches"]):
                contact_links.add(full_url)

        return {
            "ic_links": list(ic_links),
            "hr_links": list(hr_links),
            "contact_links": list(contact_links),
            "pdf_links": list(pdf_links)
        }

