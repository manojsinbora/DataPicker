"""
Unit tests for search_engine.py.
Tests multi-tiered query construction, domain exclusion filtering, and candidate deduping.
"""

import unittest
from unittest.mock import patch, MagicMock
from posh_tool.search_engine import (
    SearchEngine,
    SKIP_DOMAINS,
    REGISTRY_AGGREGATOR_DOMAINS,
    clean_entity_name,
    is_domain_relevant
)


class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SearchEngine(delay_between_queries=0.0)

    def test_build_query_tiers(self):
        """Test that query tiers are constructed covering all 5 categories."""
        queries = self.engine.build_query_tiers(city="Bangalore", area="Whitefield", industry="IT")
        self.assertGreater(len(queries), 10)

        # Check Tier 1 (POSH)
        self.assertTrue(any("Internal Committee" in q and "Bangalore" in q for q in queries))

        # Check Tier 2 (Legal entities)
        self.assertTrue(any("Private Limited" in q or "Pvt Ltd" in q for q in queries))

        # Check Tier 3 (Industry filter)
        self.assertTrue(any("IT" in q for q in queries))

        # Check Tier 4 (Area)
        self.assertTrue(any("Whitefield" in q for q in queries))

    def test_skip_domains_coverage(self):
        """Ensure non-company domains are properly blacklisted."""
        must_skip = [
            "wikipedia.org", "google.com", "microsoft.com", "linkedin.com",
            "naukri.com", "youtube.com", "tenforums.com", "ugc.gov.in"
        ]
        for d in must_skip:
            self.assertTrue(any(d in skip for skip in SKIP_DOMAINS), f"Domain {d} not in SKIP_DOMAINS")

    def test_multi_engine_fallback_to_bing(self):
        """Test that SearchEngine falls back to Bing when DuckDuckGo raises or returns empty."""
        with patch.object(self.engine, "_search_duckduckgo", return_value=[]), \
             patch.object(self.engine, "_search_bing", return_value=[{"title": "Bing Result", "href": "https://example.com", "body": "Snippet"}]):
            res = self.engine.search("test query")
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["title"], "Bing Result")
            self.assertEqual(self.engine.engine_stats["bing"], 1)

    def test_multi_engine_fallback_to_yahoo(self):
        """Test that SearchEngine falls back to Yahoo when DDG and Bing fail."""
        with patch.object(self.engine, "_search_duckduckgo", return_value=[]), \
             patch.object(self.engine, "_search_bing", return_value=[]), \
             patch.object(self.engine, "_search_yahoo", return_value=[{"title": "Yahoo Result", "href": "https://company.in", "body": "Snippet"}]):
            res = self.engine.search("test query")
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["title"], "Yahoo Result")
            self.assertEqual(self.engine.engine_stats["yahoo"], 1)

    def test_on_engine_fallback_callback(self):
        """Test that on_engine_fallback callback is invoked when a fallback engine is engaged."""
        captured = []
        engine = SearchEngine(delay_between_queries=0.0, on_engine_fallback=lambda msg: captured.append(msg))
        with patch.object(engine, "_search_duckduckgo", return_value=[]), \
             patch.object(engine, "_search_bing", return_value=[{"title": "B", "href": "https://b.com", "body": ""}]):
            res = engine.search("test query")
            self.assertEqual(len(res), 1)
            self.assertEqual(len(captured), 1)
            self.assertIn("Bing", captured[0])

    def test_bing_html_parsing_and_b64_redirect(self):
        """Test Bing HTML parsing and base64 encoded URL resolution."""
        mock_bing_html = """
        <html><body>
        <ul>
          <li class="b_algo">
            <h2><a href="https://www.bing.com/ck/a?!&&p=abc&u=a1aHR0cHM6Ly9hbHBoYWNvcnAuaW4v&ntb=1">AlphaCorp Systems</a></h2>
            <p>Leading corporate headquarters in Bengaluru.</p>
          </li>
        </ul>
        </body></html>
        """
        with patch.object(self.engine, "_get_page", return_value=mock_bing_html):
            results = self.engine._search_bing("query", max_results=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["title"], "AlphaCorp Systems")
            self.assertEqual(results[0]["href"], "https://alphacorp.in/")

    def test_yahoo_html_parsing_and_ru_redirect(self):
        """Test Yahoo HTML parsing and /RU= redirect extraction."""
        mock_yahoo_html = """
        <html><body>
        <li>
          <div class="compTitle">
            <h3><a href="https://r.search.yahoo.com/RV=2/RU=https%3a%2f%2fbetasystems.com%2fposh/RK=2/">Beta Systems POSH</a></h3>
          </div>
          <div class="compText">POSH Internal Committee details.</div>
        </li>
        </body></html>
        """
        with patch.object(self.engine, "_get_page", return_value=mock_yahoo_html):
            results = self.engine._search_yahoo("query", max_results=5)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["title"], "Beta Systems POSH")
            self.assertEqual(results[0]["href"], "https://betasystems.com/posh")

    def test_clean_entity_name(self):
        """Test entity name extraction and cleaning from MCA, LinkedIn, and Maps titles."""
        # MCA (Tofler)
        self.assertEqual(
            clean_entity_name("Bangalore Tower Financials | Company Details | Tofler"),
            "Bangalore Tower"
        )
        self.assertEqual(
            clean_entity_name("Bangalore Software Services Financials | Company Details - Tofler"),
            "Bangalore Software Services"
        )
        # MCA (ZaubaCorp)
        self.assertEqual(
            clean_entity_name("Bangalore Softsell Limited - Company Details | Zauba Corp"),
            "Bangalore Softsell Limited"
        )
        self.assertEqual(
            clean_entity_name("Triangulas Business Consulting LLP - Company Details | Zauba Corp"),
            "Triangulas Business Consulting LLP"
        )
        # LinkedIn
        self.assertEqual(
            clean_entity_name("LAKSHMI NIRMAN ( BANGALORE ) PRIVATE LIMITED | LinkedIn"),
            "LAKSHMI NIRMAN ( BANGALORE ) PRIVATE LIMITED"
        )
        self.assertEqual(
            clean_entity_name("Wipro: Overview | LinkedIn"),
            "Wipro"
        )
        # Google Maps
        self.assertEqual(
            clean_entity_name("Metec Design Engineers Private Limited - Bangalore - Google Maps"),
            "Metec Design Engineers Private Limited"
        )
        # Rejections (generic portal landing pages)
        self.assertEqual(clean_entity_name("Tofler | Company Information Website"), "")
        self.assertEqual(clean_entity_name("Zauba Corp"), "")
        self.assertEqual(clean_entity_name("Browse companies in Bangalore - LinkedIn"), "")

    def test_is_domain_relevant(self):
        """Test domain relevance checking against company name tokens."""
        # Relevant
        self.assertTrue(
            is_domain_relevant("Triangulas Business Consulting LLP", "triangulas.com")
        )
        self.assertTrue(
            is_domain_relevant("Infosys Limited", "infosys.org", "Infosys Foundation")
        )
        self.assertTrue(
            is_domain_relevant("Vasan & Sampath LLP", "vsnllp.com", "Vasan & Sampath Chartered Accountants")
        )
        # Irrelevant / spam
        self.assertFalse(
            is_domain_relevant("Vasan & Sampath LLP", "antarvasna3.com", "Spam Title", "Spam body")
        )
        self.assertFalse(
            is_domain_relevant("Metec Design", "travelguide.in", "Best Places in Bangalore", "Tour guide")
        )

    def test_build_advanced_discovery_queries(self):
        """Test construction of MCA, LinkedIn, and Google Maps discovery queries."""
        adv_queries = self.engine.build_advanced_discovery_queries(city="Bangalore", area="Whitefield", industry="IT")
        self.assertGreater(len(adv_queries), 8)

        # MCA Data coverage
        mca_queries = [q["query"] for q in adv_queries if "MCA Data" in q["source"]]
        self.assertTrue(any("tofler.in" in q and "Private Limited" in q for q in mca_queries))
        self.assertTrue(any("zaubacorp.com" in q and "LLP" in q for q in mca_queries))
        self.assertTrue(any("Limited" in q for q in mca_queries))

        # LinkedIn coverage
        linkedin_queries = [q["query"] for q in adv_queries if "LinkedIn" in q["source"]]
        self.assertTrue(any("linkedin.com/company" in q and "Private Limited" in q for q in linkedin_queries))
        self.assertTrue(any("linkedin.com/company" in q and "LLP" in q for q in linkedin_queries))

        # Google Maps coverage
        maps_queries = [q["query"] for q in adv_queries if "Google Maps" in q["source"]]
        self.assertTrue(any("google.com/maps" in q or "Google Maps" in q for q in maps_queries))

    def test_resolve_company_domain(self):
        """Test domain resolution filtering aggregators and matching corporate site."""
        mock_results = [
            {"title": "AlphaCorp on Tofler", "href": "https://www.tofler.in/alphacorp/company", "body": "Tofler details"},
            {"title": "AlphaCorp on Zauba Corp", "href": "https://www.zaubacorp.com/company/alphacorp", "body": "Zauba details"},
            {"title": "AlphaCorp Technologies Official", "href": "https://www.alphacorp.in/about", "body": "Official website"}
        ]
        with patch.object(self.engine, "search", return_value=mock_results):
            resolved = self.engine.resolve_company_domain("AlphaCorp Technologies", "Bangalore")
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved["domain"], "alphacorp.in")
            self.assertEqual(resolved["url"], "https://www.alphacorp.in/about")

    def test_iter_candidates_advanced_mode(self):
        """Test that iter_candidates with search_mode='advanced' executes advanced discovery."""
        mock_adv_cand = {
            "title": "AlphaCorp Private Limited",
            "url": "https://alphacorp.in",
            "domain": "alphacorp.in",
            "snippet": "Discovered via MCA Data"
        }
        with patch.object(self.engine, "iter_advanced_candidates", return_value=iter([mock_adv_cand])):
            with patch.object(self.engine, "build_query_tiers", return_value=[]):
                candidates = list(self.engine.iter_candidates(city="Bangalore", search_mode="advanced"))
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0]["domain"], "alphacorp.in")
                self.assertEqual(candidates[0]["title"], "AlphaCorp Private Limited")


if __name__ == "__main__":
    unittest.main()

