#!/usr/bin/env python3
"""The exit-impact maths, verified against hand-computed cases.

Wraps screener/exit_impact.py --selftest so the suite runner picks it up. The arithmetic is
what every dollar figure on the page depends on, so it is checked rather than trusted.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENER = os.path.join(os.path.dirname(HERE), "screener")

rc = subprocess.call([sys.executable, os.path.join(SCREENER, "exit_impact.py"), "--selftest"])
sys.exit(rc)
