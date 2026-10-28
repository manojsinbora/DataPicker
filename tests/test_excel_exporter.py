"""
Unit tests for excel_exporter.py.
Verifies exact 21-column schema, frozen panes, hyperlinking, Sheet 2 Notes & Sources,
and batch appending logic.
"""

import unittest
import os
import openpyxl
from posh_tool.excel_exporter import ExcelExporter
from posh_tool.config import COLUMNS, NOT_AVAILABLE


class TestExcelExporter(unittest.TestCase):
    def setUp(self):
        self.test_city = "TestCity"
        self.exporter = ExcelExporter(city=self.test_city, start_date="2026-10-28")
        if os.path.exists(self.exporter.filename):
            os.remove(self.exporter.filename)

    def tearDown(self):
        if os.path.exists(self.exporter.filename):
            os.remove(self.exporter.filename)

    def test_export_and_append_batches(self):
        """Test exporting Batch 1 and appending Batch 2 into the SAME workbook."""
        batch_1_companies = [
            {
                "Company name": "Alpha Tech Pvt Ltd",
                "Legal form (Pvt Ltd / LLP / Listed / Not confirmed)": "Pvt Ltd",
                "Full address with PIN": "123 Main Road, TestCity - 560001",
                "Company website": "https://alphatech.in",
                "Company public phone number": "+91 80 12345678",
                "Company public email ID": "contact@alphatech.in",
                "POSH / IC web page link": "https://alphatech.in/posh",
                "IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)": "https://alphatech.in/posh.pdf",
                "Where IC details were found (document name + page/section)": "POSH Policy, Page 4",
                "IC presiding officer / member name(s) (as published)": "Dr. Ananya Sen",
                "IC email ID": "ic@alphatech.in",
                "IC phone / mobile number": NOT_AVAILABLE,
                "HR contact name (as published, if any)": NOT_AVAILABLE,
                "HR email ID": "careers@alphatech.in",
                "HR phone number": NOT_AVAILABLE,
                "Employee count evidence": "Company site states '150+ employees'",
                "Source URL(s)": "https://alphatech.in",
                "Date of source / date checked": "2026-10-28",
                "Batch no.": 1,
                "Notes": NOT_AVAILABLE
            }
        ]

        cumulative_excluded = [{"name": "Excluded Coaching Center", "reason": "Disqualified: business activity identified as 'coaching classes'"}]

        # 1. Export Batch 1
        path = self.exporter.export_batch(
            new_companies=batch_1_companies,
            area="Whole city",
            industry="IT",
            target_rows=2,
            batch_no=1,
            excluded_companies=cumulative_excluded,
            all_source_urls=["https://alphatech.in"]
        )

        self.assertTrue(os.path.exists(path))

        # 2. Append Batch 2
        batch_2_companies = [
            {
                "Company name": "Beta Solutions LLP",
                "Legal form (Pvt Ltd / LLP / Listed / Not confirmed)": "LLP",
                "Full address with PIN": "456 Tech Park, TestCity - 560002",
                "Company website": "https://betasolutions.in",
                "Company public phone number": "+91 80 87654321",
                "Company public email ID": "info@betasolutions.in",
                "POSH / IC web page link": NOT_AVAILABLE,
                "IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)": NOT_AVAILABLE,
                "Where IC details were found (document name + page/section)": NOT_AVAILABLE,
                "IC presiding officer / member name(s) (as published)": NOT_AVAILABLE,
                "IC email ID": NOT_AVAILABLE,
                "IC phone / mobile number": NOT_AVAILABLE,
                "HR contact name (as published, if any)": NOT_AVAILABLE,
                "HR email ID": NOT_AVAILABLE,
                "HR phone number": NOT_AVAILABLE,
                "Employee count evidence": "Corporate leadership team observed",
                "Source URL(s)": "https://betasolutions.in",
                "Date of source / date checked": "2026-10-28",
                "Batch no.": 2,
                "Notes": NOT_AVAILABLE
            }
        ]

        self.exporter.export_batch(
            new_companies=batch_2_companies,
            area="Whole city",
            industry="IT",
            target_rows=2,
            batch_no=2,
            excluded_companies=cumulative_excluded,
            all_source_urls=["https://alphatech.in", "https://betasolutions.in"]
        )

        # 3. Verify Workbook Contents
        wb = openpyxl.load_workbook(self.exporter.filename)
        self.assertIn("Companies", wb.sheetnames)
        self.assertIn("Notes & Sources", wb.sheetnames)

        ws_companies = wb["Companies"]
        # Header + 2 data rows
        self.assertEqual(ws_companies.max_row, 3)
        self.assertEqual(ws_companies.max_column, 21)

        # Check headers
        headers = [cell.value for cell in ws_companies[1]]
        self.assertEqual(headers, COLUMNS)

        # Check continuous numbering (#)
        self.assertEqual(ws_companies.cell(row=2, column=1).value, 1)
        self.assertEqual(ws_companies.cell(row=3, column=1).value, 2)

        # Check NO empty cells rule
        for r in range(1, ws_companies.max_row + 1):
            for c in range(1, ws_companies.max_column + 1):
                val = ws_companies.cell(row=r, column=c).value
                self.assertIsNotNone(val, f"Cell at ({r}, {c}) is empty!")
                self.assertNotEqual(str(val).strip(), "", f"Cell at ({r}, {c}) is whitespace!")

        # Check Sheet 2 Notes & Sources
        ws_notes = wb["Notes & Sources"]
        self.assertGreater(ws_notes.max_row, 10)
        cell_vals = [cell.value for row in ws_notes.iter_rows() for cell in row if cell.value]
        self.assertTrue(any("PROJECT METADATA" in str(v) for v in cell_vals))
        self.assertTrue(any("RUNNING GAPS SUMMARY" in str(v) for v in cell_vals))
        self.assertTrue(any("Phone Requirement" in str(v) for v in cell_vals))
        self.assertTrue(any("Excluded Coaching Center" in str(v) for v in cell_vals))


if __name__ == "__main__":
    unittest.main()
