"""
Unit tests for main.py CLI controller and Step 1 Q1-Q6 inputs.
"""

import unittest
from unittest.mock import patch
import sys
from io import StringIO
from posh_tool.main import ask_interactive_inputs, main, run_pipeline


class TestMainCLI(unittest.TestCase):
    def test_ask_interactive_inputs_default_q6(self):
        """Test interactive prompt defaults Q6 to Basic when empty."""
        inputs = ["Bangalore", "Whitefield", "15", "IT", "optional", ""]
        with patch("builtins.input", side_effect=inputs), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            result = ask_interactive_inputs()
            self.assertEqual(result["city"], "Bangalore")
            self.assertEqual(result["area"], "Whitefield")
            self.assertEqual(result["count"], 15)
            self.assertEqual(result["industry"], "IT")
            self.assertEqual(result["require_phone"], "optional")
            self.assertEqual(result["search_mode"], "basic")
            out = mock_out.getvalue()
            self.assertIn("Search Mode: Basic", out)

    def test_ask_interactive_inputs_advanced_q6(self):
        """Test interactive prompt selects Advanced for Q6."""
        inputs = ["Mumbai", "BKC", "30", "Finance", "mandatory", "advanced"]
        with patch("builtins.input", side_effect=inputs), \
             patch("sys.stdout", new_callable=StringIO) as mock_out:
            result = ask_interactive_inputs()
            self.assertEqual(result["city"], "Mumbai")
            self.assertEqual(result["area"], "BKC")
            self.assertEqual(result["count"], 30)
            self.assertEqual(result["industry"], "Finance")
            self.assertEqual(result["require_phone"], "mandatory")
            self.assertEqual(result["search_mode"], "advanced")
            out = mock_out.getvalue()
            self.assertIn("Phone Requirement: Mandatory", out)
            self.assertIn("Search Mode: Advanced", out)

    @patch("posh_tool.main.run_pipeline")
    def test_cli_flags_search_mode_advanced(self, mock_pipeline):
        """Test that CLI flag --search-mode advanced is passed to run_pipeline."""
        test_args = [
            "main.py",
            "--city", "Pune",
            "--count", "10",
            "--search-mode", "advanced"
        ]
        with patch.object(sys, "argv", test_args):
            main()
            mock_pipeline.assert_called_once()
            _, kwargs = mock_pipeline.call_args
            self.assertEqual(kwargs["city"], "Pune")
            self.assertEqual(kwargs["count"], 10)
            self.assertEqual(kwargs["search_mode"], "advanced")


if __name__ == "__main__":
    unittest.main()
