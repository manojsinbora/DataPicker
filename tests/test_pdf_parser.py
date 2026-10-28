"""
Unit tests for pdf_parser.py.
Tests deterministic inspection of PDF documents for POSH Annexures, Presiding Officers, and emails.
"""

import unittest
from posh_tool.pdf_parser import PDFDocumentParser


# Minimal valid PDF binary with text stream
TEST_PDF_BYTES = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 180 >> stream
BT
/F1 12 Tf
72 712 Td
(Internal Committee POSH Policy Annexure 1) Tj
0 -20 Td
(Presiding Officer: Dr. Shalini Verma) Tj
0 -20 Td
(External Member: Adv. Meenakshi Sundaram) Tj
0 -20 Td
(Complaints may be sent to ic.redressal@acmecorp.in) Tj
ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000474 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
545
%%EOF"""


class TestPDFParser(unittest.TestCase):
    def setUp(self):
        self.parser = PDFDocumentParser()

    def test_parse_pdf_details(self):
        """Test extraction of Presiding Officer, IC email, and Annexure location."""
        res = self.parser.parse_pdf(TEST_PDF_BYTES, filename_hint="POSH_Policy_2025.pdf")

        self.assertTrue(res["ic_found"])
        self.assertEqual(res["presiding_officer"], "Dr. Shalini Verma")
        self.assertEqual(res["ic_email"], "ic.redressal@acmecorp.in")
        self.assertIn("Annexure", res["where_found"])
        self.assertTrue(any("Meenakshi Sundaram" in m for m in res["ic_members"]))

    def test_empty_or_corrupt_pdf(self):
        """Test handling of empty or non-PDF bytes."""
        res = self.parser.parse_pdf(b"")
        self.assertFalse(res["ic_found"])
        self.assertEqual(res["pages_count"], 0)


if __name__ == "__main__":
    unittest.main()
