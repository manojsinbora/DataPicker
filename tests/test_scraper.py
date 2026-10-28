"""
Unit tests for scraper.py.
Tests Cloudflare XOR email decoding, HTML cleanup, and page link categorization.
"""

import unittest
from bs4 import BeautifulSoup
from posh_tool.scraper import decode_cloudflare_email, WebScraper


class TestScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = WebScraper()

    def test_decode_cloudflare_email(self):
        """Test deterministic XOR decoding of Cloudflare email-protection tags."""
        # Cloudflare hex: "6e070008012e..." -> helpdeskblr@lulumall.in
        # Let's verify with a known XOR encoded string:
        # 'test@example.com' with key 0x12
        key = 0x12
        original = "test@example.com"
        hex_str = f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in original)
        decoded = decode_cloudflare_email(hex_str)
        self.assertEqual(decoded, original)

    def test_clean_html_cloudflare_replacement(self):
        """Test that __cf_email__ tags are replaced with plaintext decoded emails in HTML."""
        key = 0x55
        email = "posh@company.com"
        cf_hex = f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in email)

        html = f"""
        <div>
            <p>For POSH inquiries, contact: <a class="__cf_email__" data-cfemail="{cf_hex}">[email&#160;protected]</a></p>
        </div>
        """
        soup = self.scraper.clean_html(html)
        text = soup.get_text()
        self.assertIn("posh@company.com", text)
        self.assertNotIn("[email", text)

    def test_extract_page_links(self):
        """Test categorization of navigation and footer links."""
        base_url = "https://techcorp.in"
        html = """
        <html>
            <body>
                <nav>
                    <a href="/careers/jobs">Careers & Openings</a>
                    <a href="/about/governance/posh-policy.pdf">POSH Policy PDF</a>
                    <a href="/investors/internal-complaints-committee">Internal Committee Notice</a>
                    <a href="/contact-us">Contact Our Offices</a>
                    <a href="https://external-news.com/article">External News</a>
                </nav>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        categorized = self.scraper.extract_page_links(base_url, soup)

        self.assertTrue(any("posh-policy.pdf" in l for l in categorized["ic_links"]))
        self.assertTrue(any("internal-complaints-committee" in l for l in categorized["ic_links"]))
        self.assertTrue(any("careers" in l for l in categorized["hr_links"]))
        self.assertTrue(any("contact-us" in l for l in categorized["contact_links"]))
        self.assertTrue(any("posh-policy.pdf" in l for l in categorized["pdf_links"]))


if __name__ == "__main__":
    unittest.main()

