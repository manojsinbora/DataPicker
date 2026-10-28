"""
Public Web Search Engine interface using DuckDuckGo (zero paid APIs, 100% public).
Provides continuous candidate discovery across multi-tiered queries to satisfy high volume targets.
"""

import time
import ssl
import logging
from typing import List, Dict, Any, Optional, Iterator
from urllib.parse import urlparse

from .config import (
    CITY_ALIASES,
    CITY_LOCALITIES
)

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

# Excluded non-company domains and platforms
SKIP_DOMAINS = [
    "wikipedia.org", "merriam-webster.com", "dictionary.com", "cambridge.org",
    "vocabulary.com", "linkedin.com", "naukri.com", "indeed.com",
    "glassdoor.com", "quora.com", "youtube.com", "facebook.com", "twitter.com",
    "instagram.com", "ilovepdf.com", "zimyo.com", "keka.com", "greythr.com",
    "google.com", "microsoft.com", "apple.com", "tenforums.com", "scribd.com",
    "ugc.gov.in", "gov.in", "nic.in", "academia.edu", "researchgate.net",
    "slideshare.net", "medium.com", "reddit.com", "pinterest.com"
]


class SearchEngine:
    def __init__(self, delay_between_queries: float = 1.0):
        self.delay = delay_between_queries
        self._last_query_time = 0.0

    def search(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
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
            time.sleep(1.5)

        return results

    def build_query_tiers(self, city: str, area: str = "Whole city", industry: str = "Any") -> List[str]:
        """
        Builds a comprehensive, prioritized list of search queries across 5 tiers:
        Tier 1: Direct POSH documents & official notices in target city
        Tier 2: Major employers & registered corporate offices (Pvt Ltd, LLP, Limited)
        Tier 3: Sector & industry specific company searches
        Tier 4: Tech parks & locality-specific queries
        Tier 5: Extended directory & BRSR / Corporate Governance searches
        """
        norm_city = city.strip()
        area_clean = area.strip() if area and area.lower() not in ["whole city", "any", "none", "all"] else ""
        area_str = f" {area_clean}" if area_clean else ""
        industry_clean = industry.strip() if industry and industry.lower() not in ["any", "all", "none"] else ""
        industry_str = f" {industry_clean}" if industry_clean else ""

        # City aliases
        alias_list = CITY_ALIASES.get(norm_city.lower(), [norm_city])
        primary_city = alias_list[0].title()
        alt_city = alias_list[1].title() if len(alias_list) > 1 else primary_city

        queries = []

        # Tier 1: Direct POSH & IC Documents (High Yield for published IC details)
        queries.extend([
            f'site:*.in "Internal Committee" POSH policy {primary_city}{area_str}',
            f'"{primary_city}" "Internal Committee" POSH policy filetype:pdf',
            f'"{primary_city}" "Internal Complaints Committee" POSH policy pdf',
            f'"{primary_city}" "Presiding Officer" POSH policy{industry_str}',
            f'"{primary_city}" "sexual harassment" policy filetype:pdf{industry_str}',
            f'site:*.com "Internal Committee" POSH "{primary_city}"'
        ])
        if alt_city != primary_city:
            queries.append(f'"{alt_city}" "Internal Committee" POSH policy filetype:pdf')

        # Tier 2: Registered Corporate Offices & Legal Entities (Pvt Ltd, Limited)
        queries.extend([
            f'"{primary_city}" "Private Limited" corporate office{area_str}{industry_str}',
            f'"{primary_city}" "Pvt Ltd" headquarters{area_str}{industry_str}',
            f'"{primary_city}" "Limited" corporate office{industry_str}',
            f'top employers in "{primary_city}"{industry_str}',
            f'corporate headquarters in "{primary_city}"{industry_str}'
        ])

        # Tier 3: Industry & Sector Specific Searches
        if industry_clean:
            queries.extend([
                f'{industry_clean} companies in "{primary_city}"{area_str}',
                f'{industry_clean} corporate offices in "{primary_city}"',
                f'top {industry_clean} firms in "{primary_city}"'
            ])
        else:
            queries.extend([
                f'IT software companies in "{primary_city}"{area_str}',
                f'technology product companies in "{primary_city}"',
                f'manufacturing companies in "{primary_city}" factory OR office',
                f'pharmaceutical biotechnology companies in "{primary_city}"',
                f'fintech financial services companies in "{primary_city}"',
                f'logistics supply chain companies in "{primary_city}"'
            ])

        # Tier 4: Tech Parks & Localities for the City
        localities = CITY_LOCALITIES.get(norm_city.lower(), [])
        if area_clean:
            queries.append(f'companies in "{area_clean}" "{primary_city}"')
            queries.append(f'corporate office "{area_clean}" "{primary_city}"')
        elif localities:
            for loc in localities[:6]:
                queries.append(f'companies in "{loc}" "{primary_city}"')

        # Tier 5: Governance & Annual Reports
        queries.extend([
            f'"{primary_city}" "BRSR" POSH filetype:pdf',
            f'"{primary_city}" "Annual Report" "Internal Committee" filetype:pdf',
            f'"{primary_city}" "Code of Conduct" filetype:pdf{industry_str}'
        ])

        return queries

    def iter_candidates(self, city: str, area: str = "Whole city", industry: str = "Any") -> Iterator[Dict[str, str]]:
        """
        Continuously yields candidate companies across all query tiers without stopping at an arbitrary limit.
        """
        queries = self.build_query_tiers(city=city, area=area, industry=industry)
        seen_domains = set()

        for q in queries:
            items = self.search(q, max_results=12)
            for item in items:
                href = item["href"]
                # Skip blacklisted non-company domains
                if any(skip in href.lower() for skip in SKIP_DOMAINS):
                    continue

                domain = urlparse(href).netloc.lower()
                if not domain:
                    continue
                if domain.startswith("www."):
                    domain = domain[4:]

                if domain in seen_domains:
                    continue
                seen_domains.add(domain)

                yield {
                    "title": item["title"],
                    "url": href,
                    "domain": domain,
                    "snippet": item["body"]
                }

    def discover_companies(self, city: str, area: str = "Whole city", industry: str = "Any", limit: int = 100) -> List[Dict[str, str]]:
        """
        Discovers candidates up to the requested limit across all query tiers.
        """
        candidates = []
        for cand in self.iter_candidates(city=city, area=area, industry=industry):
            candidates.append(cand)
            if len(candidates) >= limit:
                break
        return candidates

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
                break

        return links
