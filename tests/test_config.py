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
    is_valid_indian_phone,
    classify_indian_phone,
    CITY_STD_CODES,
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
        mobiles = ["+91 9876543210", "9876543210", "+91-8888899999", "09123456789", "+91 8123456789"]
        for m in mobiles:
            self.assertTrue(bool(PHONE_REGEX.search(m)), f"Failed on {m}")

        # Landlines
        landlines = ["080-28520261", "022 22822000", "011-23344556", "+91 80 41123456", "0124-4123456"]
        for l in landlines:
            self.assertTrue(bool(PHONE_REGEX.search(l)), f"Failed on {l}")

        # Toll-Free & Shared-Cost
        toll_free = ["1800 123 4567", "1800-425-0011", "1860 266 1234", "+91 1800 123 4567"]
        for tf in toll_free:
            self.assertTrue(bool(PHONE_REGEX.search(tf)), f"Failed on {tf}")

        # Ensure PIN codes or random numbers are NOT matched as phones
        self.assertIsNone(PHONE_REGEX.search("PIN: 560001"))
        self.assertIsNone(PHONE_REGEX.search("12345678"))
        self.assertIsNone(PHONE_REGEX.search("2024-2025"))

    def test_is_valid_indian_phone(self):
        """Verify strict Indian phone number validation under DoT NNP rules."""
        valid_cases = [
            "+91 98765 43210",
            "+91-9876543210",
            "+919876543210",
            "09876543210",
            "9876543210",
            "+91 8123456789",
            "+91 7012345678",
            "+91 6398765432",
            "+91 (080) 28520261",
            "+91 80 41123456",
            "080-28520261",
            "080 28520261",
            "011-23344556",
            "+91 11 23344556",
            "022 22822000",
            "044-25361234",
            "020-25671234",
            "040-23451234",
            "0124-4123456",
            "+91 124 4123456",
            "0120-4567890",
            "0141-2345678",
            "0484-2345678",
            "1800 123 4567",
            "1800-425-0011",
            "1800 200 1234",
            "1860 266 1234",
            "+91 1800 123 4567",
            "+91 80 41123456 Ext. 102"
        ]
        for val in valid_cases:
            self.assertTrue(is_valid_indian_phone(val), f"Failed to validate valid Indian phone: {val}")

        invalid_cases = [
            "560001",           # Indian PIN code
            "110001",           # Indian PIN code
            "400051",           # Indian PIN code
            "123456",           # 6 digits
            "12345678",         # Bare 8 digits without STD
            "41123456",         # Bare 8 digits without STD
            "1234567890",       # Starts with 1, not toll-free
            "2345678901",       # Starts with 2, not 10-digit mobile
            "3456789012",       # Starts with 3
            "4567890123",       # Starts with 4
            "5678901234",       # Starts with 5
            "9999999999",       # All identical dummy digits
            "0000000000",       # All zeros
            "1111111111",       # All ones
            "8888888888",       # All eights
            "2024-2025",        # Financial year
            "+1 415 555 2671",  # US phone number
            "+44 20 7946 0919", # UK phone number
            "98765",            # 5 digits
            "98765432101234",   # Too long
            "",                 # Empty
            None                # NoneType
        ]
        for inval in invalid_cases:
            self.assertFalse(is_valid_indian_phone(inval), f"Failed to reject invalid phone: {inval}")

    def test_classify_indian_phone(self):
        """Verify functional classification of Indian phone numbers."""
        self.assertEqual(classify_indian_phone("+91 80 41123456", "Bangalore"), "Bangalore office landline")
        self.assertEqual(classify_indian_phone("080-28520261", "Bengaluru"), "Bengaluru office landline")
        self.assertEqual(classify_indian_phone("011-23344556", "Delhi"), "Delhi office landline")
        self.assertEqual(classify_indian_phone("1800 123 4567", "Bangalore"), "National toll-free number")
        self.assertEqual(classify_indian_phone("1860 266 1234", "Mumbai"), "National shared-cost number")
        self.assertEqual(classify_indian_phone("+91 9845012345", "Bangalore"), "Indian mobile number")

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

