"""Summarise shadow-mode results (candidate ranking vs the live control ranking).

    python tools/shadow_report.py                       # reads backend/var/shadow.jsonl
    python tools/shadow_report.py --file shadow.jsonl --min-samples 200

Promotion rule of thumb, printed as the verdict:
  * never promote if the candidate would route through No Travel weather the control avoids,
  * need enough requests, and the disagreements must be small enough to be worth the change.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from stats import wilson_interval

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "backend" / "var" / "shadow.jsonl"


def load(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    agree = sum(r["agree"] for r in rows)
    diff = [r for r in rows if not r["agree"]]
    lat = sorted(r["latency_ms"] for r in rows)
    return {
        "n": n,
        "agree": agree,
        "agree_ci": wilson_interval(agree, n),
        "disagree": len(diff),
        "regressions": [r for r in diff if r["no_travel_miles_delta"] > 0],
        "mean_extra_min": statistics.fmean(r["extra_minutes"] for r in diff) if diff else 0.0,
        "mean_severe_delta": statistics.fmean(r["severe_miles_delta"] for r in diff) if diff else 0.0,
        "mean_high_delta": statistics.fmean(r["high_miles_delta"] for r in diff) if diff else 0.0,
        "p50_ms": lat[n // 2] if n else 0,
        "p95_ms": lat[min(n - 1, int(n * 0.95))] if n else 0,
    }


def render(s: dict, min_samples: int) -> str:
    if s["n"] == 0:
        return "No shadow records yet."
    lo, hi = s["agree_ci"]
    out = [
        f"Requests shadowed: {s['n']}   plan latency p50={s['p50_ms']} ms  p95={s['p95_ms']} ms",
        f"Agreement with control: {s['agree'] / s['n']:.1%}  (95% CI {lo:.1%}-{hi:.1%})",
        f"Disagreements: {s['disagree']}",
    ]
    if s["disagree"]:
        out += [
            f"  when they disagree the candidate drives {s['mean_extra_min']:+.0f} min, "
            f"{s['mean_severe_delta']:+.1f} Severe mi, {s['mean_high_delta']:+.1f} High mi on average",
            f"  safety regressions (candidate has MORE No Travel miles): {len(s['regressions'])}",
        ]
    out.append("")
    if s["regressions"]:
        out.append("VERDICT: do NOT promote. The candidate chooses routes through No Travel weather the control avoids.")
    elif s["n"] < min_samples:
        out.append(f"VERDICT: keep shadowing ({s['n']} < {min_samples} samples).")
    elif s["disagree"] / s["n"] < 0.02:
        out.append("VERDICT: candidate is nearly identical to control; promotion is low value, low risk.")
    else:
        out.append("VERDICT: candidate is safe on this traffic. Review the average trade-off above; consider promoting via an A/B test.")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    ap.add_argument("--min-samples", type=int, default=200)
    args = ap.parse_args()
    if not args.file.exists():
        raise SystemExit(f"No shadow file at {args.file}. Plan some trips first.")
    print(render(summarise(load(args.file)), args.min_samples))


if __name__ == "__main__":
    main()
