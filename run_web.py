#!/usr/bin/env python3
"""
Launcher for the POSH Research Web Dashboard.
Runs a local web server providing a full interactive web page interface for POSH IC and company research.

Run:
    python3 run_web.py
Then open http://127.0.0.1:5050 in your browser.
"""

import sys
from posh_tool.web_app import app

if __name__ == "__main__":
    port = 5050
    print("=" * 65)
    print("  POSH IC & Company Research Hub (Zero AI)")
    print(f"  Web interface live at: http://127.0.0.1:{port}")
    print("  Press Ctrl+C to stop the web server.")
    print("=" * 65)
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)

