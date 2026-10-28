"""
Public Web Search Engine interface using DuckDuckGo (zero paid APIs, 100% public).
"""

import time
import ssl
import logging
from typing import List, Dict, Any, Optional

# Apply macOS LibreSSL fix for DDGS if needed
try:
    import ddgs.http_client2
    def _safe_ssl_context(verify=True):
        return ssl.create_default_context()
    ddgs.http_client2._get_random_ssl_context = _safe_ssl_context
except Exception:
    pass

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

logger = logging.getLogger(__name__)


class SearchEngine:
    def __init__(self, delay_between_queries: float = 1.2):
        self.delay = delay_between_queries
        self._last_query_time = 0.0

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Executes a web search and returns list of dicts:
        {'title': ..., 'href': ..., 'body': ...}
        """
        if DDGS is None:
            logger.error("DDGS package not installed.")
            return []

        # Polite delay between requests to avoid rate limits
        elapsed = time.time() - self._last_query_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

        results = []
        try:
            with DDGS() as ddgs:
                raw_results = ddgs.text(query, max_results=max_results)
                if raw_results:
                    for item in raw_results:
                        href = item.get("href", "")
                        if href:
                            results.append({
                                "title": item.get("title", "").strip(),
                                "href": href.strip(),
                                "body": item.get("body", "").strip()
                            })
            self._last_query_time = time.time()
        except Exception as e:
            logger.warning(f"Search query failed for '{query}': {e}")
            time.sleep(2.0)

        return results

    def discover_companies(self, city: str, area: str = "Whole city", industry: str = "Any", limit: int = 50) -> List[Dict[str, str]]:
        """
        Finds qualifying companies in the specified city, area, and industry using public web searches.
        """
        area_str = f" {area}" if area and area.lower() not in ["whole city", "none", "any", "all"] else ""
        industry_str = f" {industry}" if industry and industry.lower() not in ["any", "all", "none"] else ""
        
        queries = [
            # Direct POSH documents & official committee notices in target city (high yield)
            f"Internal Committee POSH policy {city}{area_str} filetype:pdf",
            f"Internal Complaints Committee notice {city}{area_str} pdf",
            f"Presiding Officer POSH {city}{area_str} policy",
            f"POSH policy {city}{area_str}{industry_str}",
            f"BRSR report {city} POSH filetype:pdf",
            f"Annual Report {city} Internal Committee filetype:pdf",
            # Corporate headquarters & employers in target city
            f"top companies in {city}{area_str}{industry_str}",
            f"corporate offices in {city}{area_str}{industry_str}",
            f"headquarters in {city}{industry_str}",
            f"top employers in {city}{industry_str}",
            f"IT companies in {city}{area_str}" if "it" in industry.lower() or industry_str == "" else f"{industry} companies in {city}",
            f"manufacturing companies in {city}" if industry_str == "" else f"companies in {city}{industry_str}"
        ]

        found_candidates: List[Dict[str, str]] = []
        seen_domains = set()

        # Excluded platforms and non-company domains
        skip_domains = [
            "wikipedia.org", "merriam-webster.com", "dictionary.com", "cambridge.org",
            "vocabulary.com", "linkedin.com", "naukri.com", "indeed.com",
            "glassdoor.com", "quora.com", "youtube.com", "facebook.com", "twitter.com",
            "instagram.com", "ilovepdf.com", "zimyo.com", "keka.com", "greythr.com",
            "google.com", "microsoft.com", "apple.com", "tenforums.com", "scribd.com",
            "ugc.gov.in", "gov.in", "nic.in"
        ]

        for q in queries:
            if len(found_candidates) >= limit * 2:
                break
            items = self.search(q, max_results=10)
            for item in items:
                href = item["href"]
                # Skip blacklisted domains
                if any(skip in href.lower() for skip in skip_domains):
                    continue

                # Extract base domain
                from urllib.parse import urlparse
                domain = urlparse(href).netloc.lower()
                if not domain:
                    continue
                if domain.startswith("www."):
                    domain = domain[4:]

                if domain in seen_domains:
                    continue
                seen_domains.add(domain)

                found_candidates.append({
                    "title": item["title"],
                    "url": href,
                    "domain": domain,
                    "snippet": item["body"]
                })

        return found_candidates

    def find_company_posh_links(self, domain: str, company_name: str, city: str) -> List[Dict[str, str]]:
        """
        Executes targeted web search queries from STEP 2 to find POSH / IC pages & documents.
        Optimized into consolidated queries to maximize speed and respect public search rate limits.
        """
        links = []
        seen_urls = set()

        search_tasks = [
            f"site:{domain} (POSH OR \"Internal Committee\" OR \"Presiding Officer\" OR \"sexual harassment\")",
            f'"{company_name}" POSH policy {city} pdf'
        ]

        for q in search_tasks:
            results = self.search(q, max_results=4)
            for r in results:
                href = r["href"]
                if href and href not in seen_urls:
                    seen_urls.add(href)
                    links.append(r)
            if links:
                # If we already found relevant documents from domain query, don't spam search engine
                break

        return links
