#!/usr/bin/env python3
"""
Launcher script for POSH & Company Research Tool.
Run:
    python3 run.py
or with flags:
    python3 run.py --city "Bangalore" --area "Electronic City" --count 25 --industry "IT"
"""

import sys
from posh_tool.main import main

if __name__ == "__main__":
    main()

