"""
Unit tests for extractor.py.
Tests verbatim contact extraction, legal entity detection, city/PIN matching, and exclusion rules.
"""

import unittest
from posh_tool.extractor import DataExtractor
from posh_tool.config import NOT_AVAILABLE


class TestDataExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = DataExtractor()

    def test_disqualification_rules(self):
        """Test that excluded business types are disqualified."""
        # 1. Coaching institute
        res = self.extractor.check_disqualification("We provide coaching classes for IIT-JEE exams", "testprep.in")
        self.assertIsNotNone(res)
        self.assertIn("coaching classes", res)

        # 2. Coworking space
        res = self.extractor.check_disqualification("Book a modern coworking space in Bangalore with high speed internet", "spaces-enterprise.com")
        self.assertIsNotNone(res)
        self.assertIn("coworking space", res)

        # 3. Staffing agency
        res = self.extractor.check_disqualification("Leading recruitment consultancy and staffing agency in India", "recruitment.com")
        self.assertIsNotNone(res)
        self.assertIn("recruitment consultancy", res)

    def test_no_false_positive_disqualifications(self):
        """
        CRITICAL REGRESSION TEST:
        Ensure legitimate companies using words like 'world-class', 'classes of shares',
        or 'travel classes' are NOT falsely disqualified.
        """
        legit_text = (
            "We offer world-class enterprise software solutions to Fortune 500 companies. "
            "Our company has multiple classes of common stock and delivers best in class cloud security."
        )
        res = self.extractor.check_disqualification(legit_text, "techcorp.com")
        self.assertIsNone(res, f"Falsely disqualified legitimate company: {res}")

    def test_is_city_matched_with_synonyms(self):
        """Test that city matching handles synonyms and abbreviations."""
        # Bangalore vs Bengaluru
        city_match, _ = self.extractor.is_city_matched("Headquartered in Bengaluru, Karnataka.", "Bangalore")
        self.assertTrue(city_match)

        # Gurgaon vs Gurugram
        city_match, _ = self.extractor.is_city_matched("Office located at DLF Cyber City, Gurugram.", "Gurgaon")
        self.assertTrue(city_match)

        # Mumbai vs Bombay
        city_match, _ = self.extractor.is_city_matched("Registered in Bombay, Maharashtra.", "Mumbai")
        self.assertTrue(city_match)

        # Unrelated city
        city_match, _ = self.extractor.is_city_matched("Headquartered in London, UK.", "Bangalore")
        self.assertFalse(city_match)

    def test_is_city_matched_with_pin_prefix(self):
        """Test that city matching detects Indian PIN code prefixes."""
        # 560001 is in Bangalore
        text = "Corporate Office: Tech Park, PIN Code: 560066."
        city_match, _ = self.extractor.is_city_matched(text, "Bangalore")
        self.assertTrue(city_match)

    def test_determine_legal_form(self):
        """Test legal form identification."""
        self.assertEqual(
            self.extractor.determine_legal_form("Acme Software Solutions Private Limited", "Acme"),
            "Pvt Ltd"
        )
        self.assertEqual(
            self.extractor.determine_legal_form("Nexus Advisory LLP is a partnership firm", "Nexus"),
            "LLP"
        )
        self.assertEqual(
            self.extractor.determine_legal_form("Listed on BSE: 500124 | NSE: INFOSYS", "Infosys Limited"),
            "Listed"
        )
        self.assertEqual(
            self.extractor.determine_legal_form("Some random brand name without legal suffix", "Brand"),
            "Not confirmed"
        )

    def test_extract_address_with_pin(self):
        """Test extraction of physical address with PIN."""
        text = (
            "Contact Us\n"
            "Tech Tower, 4th Floor, Electronic City Phase 1\n"
            "Hosur Road, Bengaluru - 560100, Karnataka\n"
            "Email: info@tech.com\n"
        )
        addr = self.extractor.extract_address_with_pin(text, "Bangalore")
        self.assertNotEqual(addr, NOT_AVAILABLE)
        self.assertIn("560100", addr)

    def test_extract_employee_count_evidence(self):
        """Test employee count evidence extraction."""
        text1 = "With over 350+ employees across 4 global locations, we are growing rapidly."
        self.assertIn("350", self.extractor.extract_employee_count_evidence(text1))

        text2 = "We are proud to be Great Place to Work certified."
        self.assertIn("Great Place to Work", self.extractor.extract_employee_count_evidence(text2))

    def test_extract_company_contacts(self):
        """Test verbatim extraction of company email and phone."""
        text = "General Inquiries: info@alphacorp.in | Tel: +91 80 41123456"
        phone, email = self.extractor.extract_company_contacts(text)
        self.assertEqual(email, "info@alphacorp.in")
        self.assertIn("41123456", phone)

    def test_extract_hr_contacts(self):
        """Test verbatim extraction of HR contact details."""
        text = "For recruitment queries, contact Chief People Officer: Priya Sharma at careers@alphacorp.in or call +91 9845012345."
        hr_name, hr_email, hr_phone = self.extractor.extract_hr_contacts(text)
        self.assertEqual(hr_name, "Priya Sharma")
        self.assertEqual(hr_email, "careers@alphacorp.in")
        self.assertIn("9845012345", hr_phone)

    def test_extract_posh_from_html(self):
        """Test POSH policy details extraction from HTML text."""
        html_text = (
            "POLICY ON PREVENTION OF SEXUAL HARASSMENT (POSH)\n"
            "As per the POSH Act 2013, the Internal Committee has been constituted.\n"
            "Presiding Officer: Dr. Sunita Menon\n"
            "Committee Members: Anita Rao, Ramesh Kumar\n"
            "Grievances can be emailed to ic.redressal@enterprise.com or call +91 80 23456789.\n"
        )
        res = self.extractor.extract_posh_from_html(html_text, "https://enterprise.com/posh-policy")
        self.assertTrue(res["ic_found"])
        self.assertEqual(res["presiding_officer"], "Dr. Sunita Menon")
        self.assertEqual(res["ic_email"], "ic.redressal@enterprise.com")
        self.assertIn("23456789", res["ic_phone"])


if __name__ == "__main__":
    unittest.main()
