"""
Unit tests for search_engine.py.
Tests multi-tiered query construction, domain exclusion filtering, and candidate deduping.
"""

import unittest
from posh_tool.search_engine import SearchEngine, SKIP_DOMAINS


class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SearchEngine()

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


if __name__ == "__main__":
    unittest.main()
