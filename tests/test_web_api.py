"""
Unit tests for web_app.py Flask API routes and Task Manager.
"""

import unittest
from unittest.mock import patch
import json
from posh_tool.web_app import app
from posh_tool.web_manager import WebTaskManager


class TestWebAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        self.manager = WebTaskManager()
        self.manager.stop_task()

    def test_index_route(self):
        """Test GET / renders index.html."""
        res = self.app.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"POSH IC & Compliance Research Hub", res.data)

    def test_status_route(self):
        """Test GET /api/status returns valid JSON schema."""
        res = self.app.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("status", data)
        self.assertIn("gaps", data)
        self.assertIn("companies", data)
        self.assertIn("logs", data)

    def test_start_validation(self):
        """Test POST /api/start rejects empty city."""
        res = self.app.post(
            "/api/start",
            data=json.dumps({"city": ""}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertFalse(data["success"])

    @patch.object(WebTaskManager, "start_task", return_value=True)
    def test_start_with_require_phone(self, mock_start):
        """Test POST /api/start accepts require_phone parameter."""
        res = self.app.post(
            "/api/start",
            data=json.dumps({"city": "Bangalore", "count": 25, "require_phone": "mandatory"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        mock_start.assert_called_once()
        self.assertEqual(mock_start.call_args[1]["require_phone"], "mandatory")

    def test_stop_route(self):
        """Test POST /api/stop gracefully handles stop request."""
        res = self.app.post("/api/stop")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("success", data)

    def test_download_latest_always_available(self):
        """
        REGRESSION TEST:
        Verify that even on fresh state or error, /api/download-latest delivers a valid .xlsx file.
        """
        res = self.app.get("/api/download-latest")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.assertGreater(len(res.data), 1000)


if __name__ == "__main__":
    unittest.main()

