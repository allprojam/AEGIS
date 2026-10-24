#!/usr/bin/env python3
"""Snapshot the parity test inputs into a static fixture file.

The parity harness sampled the live DefiLlama feed, so it was not hermetic: the
same commit could pass or fail depending on what the feed returned that minute.
This captures the inputs once, plus the hand-built boundary cases, so the harness
tests code rather than the network.

Run this only when the fixtures genuinely need refreshing. A passing parity run
against a frozen fixture should never change unless the code changes.

    python3 make_fixtures.py            # writes fixtures/parity_cases.json
"""
import json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures", "parity_cases.json")
SAMPLE_N = 400


def live_sample(n=SAMPLE_N):
    """Deterministic stride through the feed. Stride, not random, so a refresh is repeatable."""
    r = urllib.request.Request("https://yields.llama.fi/pools",
                               headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    d = json.loads(urllib.request.urlopen(r, timeout=30).read().decode())["data"]
    step = max(len(d) // n, 1)
    return d[::step][:n]


# Hand-built boundary cases: every threshold tested exactly at, and one unit either side.
BOUNDARY = [
    {"symbol": "ZERO-TVL",       "apy": 5, "apyBase": 5, "apyReward": 0, "tvlUsd": 0, "volumeUsd7d": 0, "count": 100},
    {"symbol": "NULLS",          "apy": 5, "apyBase": 5, "apyReward": 0, "tvlUsd": None, "volumeUsd7d": None, "count": None},
    {"symbol": "STR-NUM",        "apy": "5.5", "apyBase": "5.5", "apyReward": "0", "tvlUsd": "2000000", "volumeUsd7d": "100000", "count": "100"},
    {"symbol": "MISSING",        "symbol": "X"},
    {"symbol": "APY-ZERO",       "apy": 0, "apyBase": 0, "apyReward": 0, "tvlUsd": 5e6, "volumeUsd7d": 1e6, "count": 200},
    {"symbol": "REW-GT-APY",     "apy": 5, "apyBase": 2, "apyReward": 9, "tvlUsd": 5e6, "volumeUsd7d": 2e6, "count": 200},
    {"symbol": "NEG-APY",        "apy": -3, "apyBase": -3, "apyReward": 0, "tvlUsd": 5e6, "volumeUsd7d": 1e5, "count": 200},
    {"symbol": "STABLE-30",      "apy": 30, "apyBase": 30, "apyReward": 0, "tvlUsd": 5e7, "volumeUsd7d": 5e6, "count": 300, "stablecoin": True},
    {"symbol": "SPOT-60pct",     "apy": 5, "apyBase": 6, "apyReward": 0, "tvlUsd": 5e7, "volumeUsd7d": 5e6, "count": 300, "apyBase7d": 10},
    {"symbol": "SPOT-59pct",     "apy": 5, "apyBase": 5.9, "apyReward": 0, "tvlUsd": 5e7, "volumeUsd7d": 5e6, "count": 300, "apyBase7d": 10},
    {"symbol": "REW-50pct",      "apy": 10, "apyBase": 5, "apyReward": 5, "tvlUsd": 5e7, "volumeUsd7d": 5e6, "count": 300},
    {"symbol": "REW-51pct",      "apy": 10, "apyBase": 4.9, "apyReward": 5.1, "tvlUsd": 5e7, "volumeUsd7d": 5e6, "count": 300},
    {"symbol": "STABLE-25",      "apy": 25, "apyBase": 25, "apyReward": 0, "tvlUsd": 5e7, "volumeUsd7d": 5e6, "count": 300, "stablecoin": True},
    {"symbol": "STABLE-25.1",    "apy": 25.1, "apyBase": 25.1, "apyReward": 0, "tvlUsd": 5e7, "volumeUsd7d": 5e6, "count": 300, "stablecoin": True},
    {"symbol": "COUNT-30",       "apy": 5, "apyBase": 5, "apyReward": 0, "tvlUsd": 5e6, "volumeUsd7d": 1e6, "count": 30},
    {"symbol": "COUNT-29",       "apy": 5, "apyBase": 5, "apyReward": 0, "tvlUsd": 5e6, "volumeUsd7d": 1e6, "count": 29},
    {"symbol": "TVL-1M",         "apy": 5, "apyBase": 5, "apyReward": 0, "tvlUsd": 1000000, "volumeUsd7d": 1e6, "count": 300},
    {"symbol": "TVL-999999",     "apy": 5, "apyBase": 5, "apyReward": 0, "tvlUsd": 999999, "volumeUsd7d": 1e6, "count": 300},
    {"symbol": "TURNOVER-1pct",  "apy": 5, "apyBase": 5, "apyReward": 0, "tvlUsd": 7e6, "volumeUsd7d": 490000, "count": 300},
    {"symbol": "TURNOVER-099",   "apy": 5, "apyBase": 5, "apyReward": 0, "tvlUsd": 7e6, "volumeUsd7d": 485100, "count": 300},
    {"symbol": "OUTLIER-TRUE",   "apy": 24, "apyBase": 24, "apyReward": 0, "tvlUsd": 5e7, "volumeUsd7d": 5e6, "count": 300, "outlier": True},
    {"symbol": "OUTLIER-FALSE",  "apy": 4, "apyBase": 4, "apyReward": 0, "tvlUsd": 5e7, "volumeUsd7d": 5e6, "count": 300, "outlier": False},
]


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    print("fetching a %d-pool sample..." % SAMPLE_N)
    sample = live_sample()
    payload = {
        "_comment": "Frozen inputs for screener/test_parity.py. Refresh with make_fixtures.py.",
        "sample": sample,
        "boundary": BOUNDARY,
    }
    json.dump(payload, open(OUT, "w"), indent=1)
    print("wrote %s" % OUT)
    print("  sample pools:   %d" % len(sample))
    print("  boundary cases: %d" % len(BOUNDARY))
    print("  bytes:          %s" % format(os.path.getsize(OUT), ","))


if __name__ == "__main__":
    main()
