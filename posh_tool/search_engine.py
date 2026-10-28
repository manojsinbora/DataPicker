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

# Business registries, aggregators and directory domains to exclude when resolving official websites
REGISTRY_AGGREGATOR_DOMAINS = [
    "tofler.in", "zaubacorp.com", "instafinancials.com", "tracxn.com", "emis.com",
    "ambitionbox.com", "justdial.com", "indiamart.com", "tradeindia.com", "fundoodata.com",
    "quickr.com", "yellowpages.in", "sulekha.com", "economictimes.indiatimes.com",
    "moneycontrol.com", "bloomberg.com", "reuters.com", "techstars.com", "crunchbase.com",
    "pitchbook.com", "vccircle.com", "inc42.com", "yourstory.com", "mapsofindia.com",
    "companycheck.co.uk", "openthedatabase.com", "google.com", "maps.google.com"
]

STOP_COMPANY_TOKENS = {
    "private", "limited", "pvt", "ltd", "llp", "the", "and", "in", "of", "for",
    "services", "solutions", "technologies", "technology", "india", "consulting",
    "associates", "group", "enterprises", "systems", "corporation", "corp"
}


def clean_entity_name(title: str, url: str = "") -> str:
    """
    Cleans raw result title from MCA registries (Tofler, ZaubaCorp), LinkedIn, or Google Maps
    to obtain the clean corporate legal name.
    """
    import re
    s = title.strip()
    # Strip site brandings and pipes/hyphens
    s = re.sub(r"\s*[-|–—]\s*(?:Tofler|Zauba\s*Corp|LinkedIn|Google\s*Maps|InstaFinancials|Tracxn|AmbitionBox|Glassdoor).*$", "", s, flags=re.I)
    # Strip financials / company details
    s = re.sub(r"\s*[-|–—]?\s*(?:Financials\s*\|\s*Company\s*Details|Company\s*Details|Financials|Director\s*Details).*$", "", s, flags=re.I)
    # Strip overview / about
    s = re.sub(r"\s*:\s*(?:Overview|About|Jobs|Life).*$", "", s, flags=re.I)
    # Strip trailing city / state like " - Bangalore, Karnataka"
    s = re.sub(r"\s*[-|–—]\s*(?:Bangalore|Bengaluru|Mumbai|Delhi|Hyderabad|Chennai|Pune|Gurugram|Noida|Kolkata|Ahmedabad).*$", "", s, flags=re.I)
    s = re.sub(r"[\s\-\|–—\.]+$", "", s).strip()

    low = s.lower()
    if not s or len(s) < 3:
        if url:
            for seg in reversed(url.rstrip("/").split("/")):
                if seg and not seg.startswith("U") and not seg.startswith("AA") and len(seg) > 5:
                    candidate = seg.replace("-", " ").title()
                    if not any(portal in candidate.lower() for portal in ["tofler", "zauba", "linkedin", "company"]):
                        return candidate
        return ""
    if any(portal in low for portal in ["tofler", "zauba corp", "zaubacorp", "linkedin", "google maps", "company information website", "search companies", "company directory", "list of companies", "top companies", "browse companies"]):
        return ""
    return s


def is_domain_relevant(entity_name: str, domain: str, result_title: str = "", result_snippet: str = "") -> bool:
    """
    Validates whether a resolved domain corresponds to the target corporate entity.
    Prevents false matches from spam or directory listings.
    """
    import re
    clean = re.sub(r"[^\w\s]", " ", entity_name.lower())
    tokens = [w for w in clean.split() if len(w) >= 3 and w not in STOP_COMPANY_TOKENS]
    if not tokens:
        return True

    dom_clean = domain.lower()
    title_clean = result_title.lower()
    snippet_clean = result_snippet.lower()

    # Check if any substantive token is in the domain
    if any(t in dom_clean for t in tokens):
        return True

    # Check if substantive tokens appear in the title or snippet
    matches_in_title = sum(1 for t in tokens if t in title_clean)
    matches_in_snippet = sum(1 for t in tokens if t in snippet_clean)

    if len(tokens) == 1 and (matches_in_title >= 1 or matches_in_snippet >= 1):
        return True
    if matches_in_title >= 2 or (matches_in_title >= 1 and matches_in_snippet >= 1):
        return True

    return False


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

    def build_advanced_discovery_queries(self, city: str, area: str = "Whole city", industry: str = "Any") -> List[Dict[str, str]]:
        """
        Builds targeted public search queries to discover valid registered businesses:
        - MCA Data: Ministry of Corporate Affairs / RoC indexes (Tofler, ZaubaCorp)
        - LinkedIn Data: Official company directories
        - Google Maps: Geographic corporate business listings
        Covering Public Limited, Private Limited, and LLP corporate entities in the target geography.
        """
        norm_city = city.strip()
        area_clean = area.strip() if area and area.lower() not in ["whole city", "any", "none", "all"] else ""
        industry_clean = industry.strip() if industry and industry.lower() not in ["any", "all", "none"] else ""

        alias_list = CITY_ALIASES.get(norm_city.lower(), [norm_city])
        primary_city = alias_list[0].title()
        alt_city = alias_list[1].title() if len(alias_list) > 1 else primary_city

        queries: List[Dict[str, str]] = []

        # 1. MCA Data (Tofler & ZaubaCorp registry indexes)
        # Private Limited
        queries.append({"query": f'site:tofler.in "{primary_city}" "Private Limited" ROC', "source": "MCA Data (Tofler)"})
        queries.append({"query": f'site:zaubacorp.com/company "{primary_city}" "Private Limited"', "source": "MCA Data (ZaubaCorp)"})
        # LLP (Limited Liability Partnership)
        queries.append({"query": f'site:tofler.in "{primary_city}" "LLP" ROC', "source": "MCA Data (Tofler)"})
        queries.append({"query": f'site:zaubacorp.com/company "{primary_city}" "LLP"', "source": "MCA Data (ZaubaCorp)"})
        # Public Limited
        queries.append({"query": f'site:tofler.in "{primary_city}" "Limited" ROC', "source": "MCA Data (Tofler)"})
        queries.append({"query": f'site:zaubacorp.com/company "{primary_city}" "Limited"', "source": "MCA Data (ZaubaCorp)"})

        if alt_city != primary_city:
            queries.append({"query": f'site:tofler.in "{alt_city}" "Private Limited" ROC', "source": "MCA Data (Tofler)"})
            queries.append({"query": f'site:zaubacorp.com/company "{alt_city}" "Private Limited"', "source": "MCA Data (ZaubaCorp)"})

        if area_clean:
            queries.append({"query": f'site:tofler.in "{primary_city}" "{area_clean}" "Private Limited"', "source": "MCA Data (Tofler)"})
            queries.append({"query": f'site:zaubacorp.com/company "{primary_city}" "{area_clean}"', "source": "MCA Data (ZaubaCorp)"})

        if industry_clean:
            queries.append({"query": f'site:tofler.in "{primary_city}" "{industry_clean}" "Private Limited"', "source": "MCA Data (Tofler)"})
            queries.append({"query": f'site:zaubacorp.com/company "{primary_city}" "{industry_clean}"', "source": "MCA Data (ZaubaCorp)"})

        # 2. LinkedIn Company Directories
        queries.append({"query": f'site:linkedin.com/company "{primary_city}" "Private Limited"', "source": "LinkedIn Directory"})
        queries.append({"query": f'site:linkedin.com/company "{primary_city}" "LLP"', "source": "LinkedIn Directory"})
        queries.append({"query": f'site:linkedin.com/company "{primary_city}" "Limited"', "source": "LinkedIn Directory"})

        if alt_city != primary_city:
            queries.append({"query": f'site:linkedin.com/company "{alt_city}" "Private Limited"', "source": "LinkedIn Directory"})

        if area_clean:
            queries.append({"query": f'site:linkedin.com/company "{primary_city}" "{area_clean}" "Private Limited"', "source": "LinkedIn Directory"})

        if industry_clean:
            queries.append({"query": f'site:linkedin.com/company "{primary_city}" "{industry_clean}" "Private Limited"', "source": "LinkedIn Directory"})

        # 3. Google Maps / Geographic Business Listings
        queries.append({"query": f'site:google.com/maps "{primary_city}" "Private Limited"', "source": "Google Maps"})
        queries.append({"query": f'"{primary_city}" "Private Limited" "Google Maps"', "source": "Google Maps"})
        queries.append({"query": f'site:google.com/maps "{primary_city}" "LLP"', "source": "Google Maps"})
        queries.append({"query": f'"{primary_city}" "LLP" "Google Maps"', "source": "Google Maps"})
        queries.append({"query": f'site:google.com/maps "{primary_city}" "Limited"', "source": "Google Maps"})
        queries.append({"query": f'"corporate office" "{primary_city}" "Google Maps"', "source": "Google Maps"})

        if area_clean:
            queries.append({"query": f'site:google.com/maps "{primary_city}" "{area_clean}"', "source": "Google Maps"})
            queries.append({"query": f'"{area_clean}" "{primary_city}" "Google Maps"', "source": "Google Maps"})

        return queries

    def resolve_company_domain(self, entity_name: str, city: str) -> Optional[Dict[str, str]]:
        """
        Resolves a verified corporate entity name to its official company website.
        Filters out registries, aggregators, job boards, and spam sites.
        """
        # Primary search: official website
        query = f'"{entity_name}" official website'
        results = self.search(query, max_results=5)
        for r in results:
            href = r.get("href", "")
            if not href.startswith("http"):
                continue
            dom = urlparse(href).netloc.lower()
            if dom.startswith("www."):
                dom = dom[4:]
            if not dom:
                continue
            if any(skip in dom for skip in SKIP_DOMAINS) or any(reg in dom for reg in REGISTRY_AGGREGATOR_DOMAINS):
                continue
            if is_domain_relevant(entity_name, dom, r.get("title", ""), r.get("body", "")):
                return {
                    "domain": dom,
                    "url": href,
                    "title": r.get("title", entity_name)
                }

        # Secondary search: city corporate website
        query_alt = f'{entity_name} {city} corporate website'
        results_alt = self.search(query_alt, max_results=4)
        for r in results_alt:
            href = r.get("href", "")
            if not href.startswith("http"):
                continue
            dom = urlparse(href).netloc.lower()
            if dom.startswith("www."):
                dom = dom[4:]
            if not dom:
                continue
            if any(skip in dom for skip in SKIP_DOMAINS) or any(reg in dom for reg in REGISTRY_AGGREGATOR_DOMAINS):
                continue
            if is_domain_relevant(entity_name, dom, r.get("title", ""), r.get("body", "")):
                return {
                    "domain": dom,
                    "url": href,
                    "title": r.get("title", entity_name)
                }

        return None

    def iter_advanced_candidates(
        self,
        city: str,
        area: str = "Whole city",
        industry: str = "Any"
    ) -> Iterator[Dict[str, str]]:
        """
        Advanced Discovery:
        Queries MCA Data (Tofler, ZaubaCorp), LinkedIn directories, and Google Maps listings
        for Public Limited, Private Limited, and LLP corporate entities in the target geography,
        extracts clean registered entity names, resolves them to official corporate domains,
        and yields candidates.
        """
        discovery_queries = self.build_advanced_discovery_queries(city=city, area=area, industry=industry)
        seen_entities = set()
        seen_domains = set()

        for q_item in discovery_queries:
            q_text = q_item["query"]
            source_tag = q_item["source"]
            items = self.search(q_text, max_results=8)
            for item in items:
                raw_title = item.get("title", "")
                raw_href = item.get("href", "")
                entity_name = clean_entity_name(raw_title, raw_href)
                if not entity_name:
                    continue

                entity_key = entity_name.lower()
                if entity_key in seen_entities:
                    continue
                seen_entities.add(entity_key)

                resolved = self.resolve_company_domain(entity_name, city)
                if not resolved:
                    continue

                dom = resolved["domain"]
                if dom in seen_domains:
                    continue
                seen_domains.add(dom)

                yield {
                    "title": entity_name,
                    "url": resolved["url"],
                    "domain": dom,
                    "snippet": f"Discovered via {source_tag} in {city} ({item.get('body', '')[:100]})",
                    "discovery_source": source_tag
                }

    def iter_candidates(
        self,
        city: str,
        area: str = "Whole city",
        industry: str = "Any",
        search_mode: str = "basic"
    ) -> Iterator[Dict[str, str]]:
        """
        Continuously yields candidate companies across all query tiers without stopping at an arbitrary limit.
        If search_mode == 'advanced':
          Discovers registered businesses via MCA Data, LinkedIn, and Google Maps (Pvt Ltd, Limited, LLP)
          first, resolves to company domains, and seamlessly continues into standard query tiers.
        If search_mode == 'basic':
          Directly executes standard multi-tiered public search queries.
        """
        seen_domains = set()

        if search_mode and search_mode.lower() == "advanced":
            for cand in self.iter_advanced_candidates(city=city, area=area, industry=industry):
                domain = cand["domain"]
                if domain in seen_domains:
                    continue
                seen_domains.add(domain)
                yield cand

        # Standard query tiers (continuous fallback)
        queries = self.build_query_tiers(city=city, area=area, industry=industry)
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

    def discover_companies(
        self,
        city: str,
        area: str = "Whole city",
        industry: str = "Any",
        limit: int = 100,
        search_mode: str = "basic"
    ) -> List[Dict[str, str]]:
        """
        Discovers candidates up to the requested limit across query tiers.
        """
        candidates = []
        for cand in self.iter_candidates(city=city, area=area, industry=industry, search_mode=search_mode):
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
