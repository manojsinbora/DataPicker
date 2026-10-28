"""
Unit tests for web_app.py Flask API routes and Task Manager.
"""

import unittest
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

    def test_stop_route(self):
        """Test POST /api/stop gracefully handles stop request."""
        res = self.app.post("/api/stop")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("success", data)


if __name__ == "__main__":
    unittest.main()
