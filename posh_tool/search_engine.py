"""
Public Multi-Engine Web Search interface with zero-paid scraping fallbacks.
100% public sources, zero paid APIs, zero AI.
Engines: DuckDuckGo (Primary) -> Bing -> Yahoo -> Google -> SearXNG.
Provides continuous candidate discovery across multi-tiered queries to satisfy high volume targets.
"""

import time
import ssl
import logging
import base64
from typing import List, Dict, Any, Optional, Iterator, Callable
from urllib.parse import urlparse, unquote, quote_plus

import requests
from bs4 import BeautifulSoup

from .config import (
    CITY_ALIASES,
    CITY_LOCALITIES,
    DEFAULT_USER_AGENT
)

try:
    import primp
    HAS_PRIMP = True
except ImportError:
    HAS_PRIMP = False

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
    ENGINE_CASCADE = ["duckduckgo", "bing", "yahoo", "google", "searxng"]

    def __init__(
        self,
        delay_between_queries: float = 1.0,
        enabled_engines: Optional[List[str]] = None,
        on_engine_fallback: Optional[Callable[[str], None]] = None
    ):
        self.delay = delay_between_queries
        self._last_query_time = 0.0
        self.enabled_engines = enabled_engines or list(self.ENGINE_CASCADE)
        self.engine_stats: Dict[str, int] = {e: 0 for e in self.ENGINE_CASCADE}
        self.on_engine_fallback = on_engine_fallback

        if HAS_PRIMP:
            try:
                self.client = primp.Client(impersonate="chrome_124", verify=False, timeout=10)
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

    def _get_page(self, url: str) -> Optional[str]:
        """Fetches page content with TLS impersonation or standard requests session."""
        if self.client:
            try:
                resp = self.client.get(url)
                if resp.status_code == 200:
                    return resp.text
            except Exception:
                pass
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return None

    def _search_duckduckgo(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Primary search: DuckDuckGo public API."""
        if DDGS is None:
            return []
        results = []
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
        return results

    def _search_bing(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Fallback 1: Public Bing search scraping with base64 redirect resolution."""
        url = f"https://www.bing.com/search?q={quote_plus(query)}"
        html = self._get_page(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for li in soup.select("li.b_algo"):
            h2 = li.find("h2")
            a = h2.find("a") if h2 else None
            p = li.find("p")
            if a and a.get("href"):
                href = a["href"]
                # Resolve Bing redirect if present
                if "bing.com/ck/a" in href and "&u=" in href:
                    try:
                        u = href.split("&u=")[1].split("&")[0]
                        if u.startswith("a1"):
                            b64 = u[2:] + "=" * ((4 - len(u[2:]) % 4) % 4)
                            href = base64.urlsafe_b64decode(b64).decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                results.append({
                    "title": a.get_text(strip=True),
                    "href": href.strip(),
                    "body": p.get_text(strip=True) if p else ""
                })
                if len(results) >= max_results:
                    break
        return results

    def _search_yahoo(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Fallback 2: Public Yahoo search scraping with /RU= redirect resolution."""
        url = f"https://search.yahoo.com/search?p={quote_plus(query)}"
        html = self._get_page(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for div in soup.find_all("div", class_="compTitle"):
            a = div.find("a")
            if not a:
                continue
            raw_href = a.get("href", "")
            if "/RU=" in raw_href:
                try:
                    actual_url = unquote(raw_href.split("/RU=")[1].split("/RK=")[0])
                except Exception:
                    actual_url = raw_href
            else:
                actual_url = raw_href

            if not actual_url.startswith("http") or "yahoo.com" in actual_url:
                continue

            h3 = div.find("h3") or div.find("h4")
            title = h3.get_text(strip=True) if h3 else a.get_text(strip=True)
            parent_li = div.find_parent("li")
            snippet = ""
            if parent_li:
                comp_text = parent_li.find("div", class_="compText")
                if comp_text:
                    snippet = comp_text.get_text(strip=True)

            results.append({
                "title": title.strip(),
                "href": actual_url.strip(),
                "body": snippet.strip()
            })
            if len(results) >= max_results:
                break
        return results

    def _search_google(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Fallback 3: Public Google search scraping."""
        url = f"https://www.google.com/search?q={quote_plus(query)}&hl=en&num={max_results}"
        html = self._get_page(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for div in soup.select("div.g"):
            a = div.find("a")
            h3 = div.find("h3")
            if a and h3 and a.get("href", "").startswith("http"):
                snippet_div = div.find("div", class_="VwiC3b")
                results.append({
                    "title": h3.get_text(strip=True),
                    "href": a["href"].strip(),
                    "body": snippet_div.get_text(strip=True) if snippet_div else ""
                })
                if len(results) >= max_results:
                    break

        if not results:
            for a in soup.find_all("a"):
                href = a.get("href", "")
                if "/url?q=" in href:
                    try:
                        target = unquote(href.split("/url?q=")[1].split("&")[0])
                        if target.startswith("http") and "google.com" not in target:
                            title = a.get_text(strip=True)
                            if title and len(title) > 3:
                                results.append({"title": title, "href": target, "body": ""})
                                if len(results) >= max_results:
                                    break
                    except Exception:
                        pass
        return results

    def _search_searxng(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Fallback 4: Public open-source SearXNG instance meta-search."""
        public_nodes = [
            "https://searx.tiekoetter.com",
            "https://searx.be",
            "https://baresearch.org",
            "https://priv.au",
            "https://search.mdosch.de"
        ]
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        for node in public_nodes:
            try:
                resp = requests.get(f"{node}/search", params={"q": query, "format": "json"}, headers=headers, timeout=4)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_items = data.get("results", [])
                    results = []
                    for item in raw_items:
                        url = item.get("url", "")
                        if url.startswith("http"):
                            results.append({
                                "title": item.get("title", "").strip(),
                                "href": url.strip(),
                                "body": item.get("content", "").strip()
                            })
                            if len(results) >= max_results:
                                break
                    if results:
                        return results
            except Exception:
                continue
        return []

    def search(self, query: str, max_results: int = 10, preferred_engine: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Executes a web search with resilient zero-paid multi-engine cascading fallback:
        DuckDuckGo -> Bing -> Yahoo -> Google -> SearXNG.
        
        Guarantees 100% zero-paid-API compliance using only public search interfaces.
        """
        # Polite delay between requests to avoid rate limits
        elapsed = time.time() - self._last_query_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

        engine_order = list(self.enabled_engines)
        if preferred_engine and preferred_engine in engine_order:
            engine_order.remove(preferred_engine)
            engine_order.insert(0, preferred_engine)

        for idx, engine_name in enumerate(engine_order):
            try:
                if idx > 0 and self.on_engine_fallback:
                    self.on_engine_fallback(f"[Public Search Fallback] Engaged {engine_name.title()} public search for query: {query[:60]}...")
                results = []
                if engine_name == "duckduckgo":
                    results = self._search_duckduckgo(query, max_results)
                elif engine_name == "bing":
                    results = self._search_bing(query, max_results)
                elif engine_name == "yahoo":
                    results = self._search_yahoo(query, max_results)
                elif engine_name == "google":
                    results = self._search_google(query, max_results)
                elif engine_name == "searxng":
                    results = self._search_searxng(query, max_results)

                if results:
                    self.engine_stats[engine_name] = self.engine_stats.get(engine_name, 0) + 1
                    self._last_query_time = time.time()
                    return results[:max_results]
                else:
                    logger.debug(f"Search engine '{engine_name}' returned 0 results for '{query}'. Trying next fallback...")
            except Exception as e:
                logger.warning(f"Search engine '{engine_name}' failed for '{query}': {e}. Trying next fallback...")
                time.sleep(0.5)

        self._last_query_time = time.time()
        return []

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
