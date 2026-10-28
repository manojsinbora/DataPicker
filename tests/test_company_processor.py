"""
Unit tests for company_processor.py.
Tests end-to-end processing pipeline, mock fetching, qualification, and data assembly.
"""

import unittest
from unittest.mock import MagicMock
from posh_tool.company_processor import CompanyProcessor
from posh_tool.scraper import WebScraper
from posh_tool.config import NOT_AVAILABLE


class TestCompanyProcessor(unittest.TestCase):
    def setUp(self):
        self.mock_search = MagicMock()
        self.real_scraper = WebScraper()
        self.mock_scraper = MagicMock()
        # Delegate HTML parsing to real WebScraper methods
        self.mock_scraper.clean_html.side_effect = self.real_scraper.clean_html
        self.mock_scraper.extract_page_links.side_effect = self.real_scraper.extract_page_links
        self.processor = CompanyProcessor(search_engine=self.mock_search, scraper=self.mock_scraper)

    def test_process_qualifying_company(self):
        """Test processing a legitimate qualified corporate employer."""
        candidate = {
            "title": "Zenith Tech Systems Pvt Ltd",
            "url": "https://zenithtech.in",
            "domain": "zenithtech.in",
            "snippet": "Leading IT services company in Bengaluru"
        }

        # Mock HTML response
        home_html = """
        <html>
            <head><title>Zenith Tech Systems Private Limited</title></head>
            <body>
                <p>Welcome to Zenith Tech Systems Private Limited, Bengaluru.</p>
                <p>We are a team of 250+ employees.</p>
                <p>Address: Tech Park, Electronic City, Bengaluru - 560100</p>
                <a href="/contact">Contact</a>
                <a href="/careers">Careers</a>
                <a href="/posh-policy.pdf">POSH Policy</a>
            </body>
        </html>
        """
        self.mock_scraper.fetch_url.return_value = (home_html, b"mock", 200)

        record, exclusion, sources = self.processor.process_company(
            candidate=candidate,
            target_city="Bangalore",
            target_area="Whole city",
            batch_no=1
        )

        self.assertIsNone(exclusion)
        self.assertIsNotNone(record)
        self.assertIn("Zenith Tech Systems", record["Company name"])
        self.assertEqual(record["Legal form (Pvt Ltd / LLP / Listed / Not confirmed)"], "Pvt Ltd")
        self.assertIn("560100", record["Full address with PIN"])
        self.assertIn("250", record["Employee count evidence"])

    def test_process_excluded_coaching_center(self):
        """Test exclusion of coaching institutes."""
        candidate = {
            "title": "Premier Coaching Classes",
            "url": "https://premiercoaching.in",
            "domain": "premiercoaching.in",
            "snippet": "Coaching classes for competitive exams in Bangalore"
        }

        home_html = "<html><body>We provide coaching classes for IIT-JEE exams in Bengaluru.</body></html>"
        self.mock_scraper.fetch_url.return_value = (home_html, b"", 200)

        record, exclusion, _ = self.processor.process_company(
            candidate=candidate,
            target_city="Bangalore",
            target_area="Whole city",
            batch_no=1
        )

        self.assertIsNone(record)
        self.assertIsNotNone(exclusion)
        self.assertIn("coaching", exclusion["reason"])

    def test_process_location_mismatch(self):
        """Test exclusion when company is not in target city."""
        candidate = {
            "title": "North India Steel Works Pvt Ltd",
            "url": "https://northesteel.in",
            "domain": "northsteel.in",
            "snippet": "Steel manufacturing in Ludhiana, Punjab"
        }

        home_html = "<html><body>Factory and registered office located in Ludhiana, Punjab - 141001.</body></html>"
        self.mock_scraper.fetch_url.return_value = (home_html, b"", 200)
        self.mock_search.search.return_value = []  # No search results for Bangalore

        record, exclusion, _ = self.processor.process_company(
            candidate=candidate,
            target_city="Bangalore",
            target_area="Whole city",
            batch_no=1
        )

        self.assertIsNone(record)
        self.assertIsNotNone(exclusion)
        self.assertIn("No confirmed physical presence found in Bangalore", exclusion["reason"])


if __name__ == "__main__":
    unittest.main()
