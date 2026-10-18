"""Deployment shadow test: replay identical requests against the live deployment and a candidate
deployment, then diff the answers. The candidate never serves users; only this script talks to it.

    python tools/shadow_replay.py --primary https://live.example --candidate https://staging.example -n 50

Compared per trip: number of routes, recommended route, rank order, and risk metrics (within a
tolerance, because forecasts refresh between the two calls). Exit code 1 if too many trips differ,
so it can gate a release in CI.
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "loadtests"))
from trips import make_trip  # noqa: E402

MILE_TOLERANCE = 25.0  # forecast refresh can move a few segments
TIME_TOLERANCE_MIN = 20.0


def call(base: str, trip: dict) -> tuple[dict | None, float]:
    started = time.monotonic()
    try:
        r = requests.post(f"{base}/api/plan/", json=trip, timeout=120)
        return (r.json() if r.status_code == 200 else None), (time.monotonic() - started) * 1000
    except requests.RequestException:
        return None, (time.monotonic() - started) * 1000


def diff(a: dict, b: dict) -> list[str]:
    problems = []
    if len(a["routes"]) != len(b["routes"]):
        return [f"route count {len(a['routes'])} vs {len(b['routes'])}"]
    if a["recommended_id"] != b["recommended_id"]:
        problems.append(f"recommended {a['recommended_id']} vs {b['recommended_id']}")
    ra = {r["id"]: r for r in a["routes"]}
    rb = {r["id"]: r for r in b["routes"]}
    for rid in ra:
        if rid not in rb:
            problems.append(f"route {rid} missing on candidate")
            continue
        x, y = ra[rid], rb[rid]
        for key in ("no_travel_miles", "severe_miles", "high_miles"):
            if abs(x["metrics"][key] - y["metrics"][key]) > MILE_TOLERANCE:
                problems.append(f"{rid}.{key} {x['metrics'][key]} vs {y['metrics'][key]}")
        if abs(x["duration_s"] - y["duration_s"]) / 60 > TIME_TOLERANCE_MIN:
            problems.append(f"{rid} duration {x['duration_s'] / 60:.0f} vs {y['duration_s'] / 60:.0f} min")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--max-diff-ratio", type=float, default=0.1)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    mismatches, errors, lat_a, lat_b = 0, 0, [], []
    for i in range(args.n):
        trip = make_trip(rng)
        a, ta = call(args.primary.rstrip("/"), trip)
        b, tb = call(args.candidate.rstrip("/"), trip)
        lat_a.append(ta)
        lat_b.append(tb)
        name = f"{trip['origin']['label']} -> {trip['destination']['label']} @{trip['load_lb']}lb"
        if a is None or b is None:
            errors += 1
            print(f"[{i + 1:>3}] ERROR    {name}: primary={'ok' if a else 'fail'} candidate={'ok' if b else 'fail'}")
            continue
        problems = diff(a, b)
        mismatches += bool(problems)
        print(f"[{i + 1:>3}] {'DIFF' if problems else 'same'}     {name}" + (": " + "; ".join(problems) if problems else ""))

    compared = args.n - errors
    ratio = mismatches / compared if compared else 1.0
    print(f"\nCompared {compared}/{args.n} trips; {mismatches} differ ({ratio:.0%}); {errors} errors")
    if lat_a and lat_b:
        print(f"Latency median: primary {statistics.median(lat_a):.0f} ms, candidate {statistics.median(lat_b):.0f} ms")
    bad = errors > 0 or ratio > args.max_diff_ratio
    print("RESULT: " + ("FAIL - do not promote the candidate" if bad else "PASS - candidate matches the live deployment"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
