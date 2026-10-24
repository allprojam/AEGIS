#!/usr/bin/env python3
"""The forward-breach simulation, verified against hand-computed cases.

Wraps screener/stress_forward.py --selftest. Includes the check that the Monte Carlo agrees
with the closed form in DISCRIMINATING cases -- an earlier version of the closed form used
`margin` where the correct numerator is -ln(1-margin), and the original test cases all sat near
zero, where both forms agree, so they passed trivially and hid a 7x error at large margins.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENER = os.path.join(os.path.dirname(HERE), "screener")

rc = subprocess.call([sys.executable, os.path.join(SCREENER, "stress_forward.py"), "--selftest"])
sys.exit(rc)
