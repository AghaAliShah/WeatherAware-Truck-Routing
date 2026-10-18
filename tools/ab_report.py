"""A/B report for the `why_default` experiment.

    python tools/ab_report.py                       # reads backend/var/event.jsonl
    python tools/ab_report.py --file events.jsonl --min-per-arm 100

Unit of analysis is the visitor, counted only if they were *exposed* (saw the recommendation).
Primary metric: opened a checkpoint. Guardrails: selected a route, used the forecast slider.
Also reports a sample-ratio-mismatch (SRM) check; if that fails, do not trust the results.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from stats import required_sample_per_arm, sample_ratio_mismatch, two_proportion_test, wilson_interval

METRICS = [
    ("checkpoint_opened", "PRIMARY  opened a checkpoint"),
    ("route_selected", "guardrail selected a route"),
    ("slider_used", "guardrail used forecast slider"),
    ("why_toggled", "info      toggled 'Why this route?'"),
]
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "backend" / "var" / "event.jsonl"


def load(path: Path, experiment: str) -> dict[str, dict[str, set[str]]]:
    """variant -> event -> set of visitors."""
    data: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("experiment") == experiment:
            data[row["variant"]][row["event"]].add(row["visitor"])
    return data


def analyse(data: dict[str, dict[str, set[str]]], control: str, treatment: str) -> dict:
    exposed = {v: data[v]["exposure"] for v in (control, treatment)}
    n = {v: len(exposed[v]) for v in exposed}
    report = {"n": n, "srm_p": sample_ratio_mismatch(n[control], n[treatment]), "metrics": []}
    for event, label in METRICS:
        x = {v: len(data[v][event] & exposed[v]) for v in exposed}
        test = two_proportion_test(x[control], n[control], x[treatment], n[treatment])
        report["metrics"].append(
            {
                "event": event,
                "label": label,
                "x": x,
                "rate": {v: (x[v] / n[v] if n[v] else 0.0) for v in x},
                "ci": {v: wilson_interval(x[v], n[v]) for v in x},
                **test,
            }
        )
    return report


def render(report: dict, control: str, treatment: str, min_per_arm: int) -> str:
    n = report["n"]
    out = [f"Exposed visitors: {control}={n[control]}  {treatment}={n[treatment]}"]
    srm = report["srm_p"]
    out.append(f"Sample ratio check (50/50): p={srm:.4f} -> {'OK' if srm >= 0.001 else 'MISMATCH: assignment or logging is broken, results are not trustworthy'}")
    out.append("")
    out.append(f"{'metric':38}{control:>16}{treatment:>16}{'diff (95% CI)':>26}{'p':>8}")
    for m in report["metrics"]:
        c, t = m["rate"][control], m["rate"][treatment]
        lo, hi = m["ci"]
        out.append(
            f"{m['label']:38}{c:>15.1%} {t:>15.1%} {m['diff']:>+10.1%} ({lo:+.1%}, {hi:+.1%}){m['p_value']:>8.3f}"
        )
    out.append("")
    smallest = min(n.values())
    primary = report["metrics"][0]
    if smallest < min_per_arm:
        base = max(primary["rate"][control], 0.05)
        need = required_sample_per_arm(base, 0.2)
        out.append(
            f"VERDICT: keep collecting. {smallest} < {min_per_arm} exposed visitors in the smaller arm "
            f"(about {need} per arm are needed to detect a 20% relative lift at baseline {base:.0%})."
        )
    elif primary["p_value"] < 0.05 and primary["diff"] > 0:
        out.append(f"VERDICT: ship '{treatment}'. Primary metric improved significantly; check the guardrails above did not drop.")
    elif primary["p_value"] < 0.05:
        out.append(f"VERDICT: keep '{control}'. '{treatment}' significantly reduced the primary metric.")
    else:
        out.append("VERDICT: no detectable difference. Keep the simpler variant (control) unless the guardrails say otherwise.")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=DEFAULT_FILE)
    ap.add_argument("--experiment", default="why_default")
    ap.add_argument("--control", default="control")
    ap.add_argument("--treatment", default="open")
    ap.add_argument("--min-per-arm", type=int, default=100)
    args = ap.parse_args()
    if not args.file.exists():
        raise SystemExit(f"No event file at {args.file}. Use the app (or Locust) first, or pass --file.")
    data = load(args.file, args.experiment)
    print(render(analyse(data, args.control, args.treatment), args.control, args.treatment, args.min_per_arm))


if __name__ == "__main__":
    main()
