"""
Unit tests for config.py.
Verifies columns, regex patterns, city aliases, and exclusion rules.
"""

import unittest
import re
from posh_tool.config import (
    COLUMNS,
    EMAIL_REGEX,
    PHONE_REGEX,
    PIN_CODE_REGEX,
    EMPLOYEE_COUNT_REGEX,
    CITY_ALIASES,
    CITY_PIN_PREFIXES,
    NOT_AVAILABLE
)


class TestConfig(unittest.TestCase):
    def test_columns_count_and_order(self):
        """Verify exact 21 columns in mandatory order."""
        self.assertEqual(len(COLUMNS), 21)
        expected_first_5 = [
            "#",
            "Company name",
            "Legal form (Pvt Ltd / LLP / Listed / Not confirmed)",
            "Full address with PIN",
            "Company website"
        ]
        self.assertEqual(COLUMNS[:5], expected_first_5)
        self.assertEqual(COLUMNS[11], "IC email ID")
        self.assertEqual(COLUMNS[12], "IC phone / mobile number")
        self.assertEqual(COLUMNS[14], "HR email ID")
        self.assertEqual(COLUMNS[20], "Notes")

    def test_email_regex(self):
        """Verify strict email extraction."""
        text = "Contact us at posh.officer@domain.co.in or hr_team@company.org."
        matches = EMAIL_REGEX.findall(text)
        self.assertEqual(matches, ["posh.officer@domain.co.in", "hr_team@company.org"])

    def test_phone_regex(self):
        """Verify Indian mobile and landline regex."""
        # Mobiles
        mobiles = ["+91 9876543210", "9876543210", "+91-8888899999", "09123456789"]
        for m in mobiles:
            self.assertTrue(bool(PHONE_REGEX.search(m)), f"Failed on {m}")

        # Landlines
        landlines = ["080-28520261", "022 22822000", "011-23344556"]
        for l in landlines:
            self.assertTrue(bool(PHONE_REGEX.search(l)), f"Failed on {l}")

    def test_pin_code_regex(self):
        """Verify Indian 6-digit PIN code extraction."""
        self.assertEqual(PIN_CODE_REGEX.search("Bangalore 560001 Karnataka").group(1), "560001")
        self.assertEqual(PIN_CODE_REGEX.search("Mumbai 400051").group(1), "400051")
        # Reject 5-digit or 7-digit numbers
        self.assertIsNone(PIN_CODE_REGEX.search("12345"))
        self.assertIsNone(PIN_CODE_REGEX.search("1234567"))

    def test_employee_count_regex(self):
        """Verify employee count phrase extraction."""
        m = EMPLOYEE_COUNT_REGEX.search("We are a team of 450+ employees across India.")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "450")

        m2 = EMPLOYEE_COUNT_REGEX.search("Empowering over 1,200 team members globally.")
        self.assertIsNotNone(m2)
        self.assertEqual(m2.group(1), "1,200")

    def test_city_aliases(self):
        """Verify city normalization mappings."""
        self.assertIn("bengaluru", CITY_ALIASES["bangalore"])
        self.assertIn("gurugram", CITY_ALIASES["gurgaon"])
        self.assertIn("bombay", CITY_ALIASES["mumbai"])


if __name__ == "__main__":
    unittest.main()
