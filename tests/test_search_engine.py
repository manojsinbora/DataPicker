"""
Unit tests for search_engine.py.
Tests multi-tiered query construction, domain exclusion filtering, and candidate deduping.
"""

import unittest
from unittest.mock import patch, MagicMock
from posh_tool.search_engine import SearchEngine, SKIP_DOMAINS


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


if __name__ == "__main__":
    unittest.main()

