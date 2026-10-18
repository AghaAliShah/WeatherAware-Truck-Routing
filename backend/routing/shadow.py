"""Shadow evaluation of a candidate ranking policy.

The *control* policy (spec order: No Travel, Severe, High, average risk, time) always decides what the
user sees. The *candidate* policy is evaluated on the same data for every request, its choice is
logged next to the control's, and it never influences the response. Reviewing the disagreement rate
and the cost of the disagreements (see tools/shadow_report.py) is how a ranking change gets
validated on real traffic before it is promoted.

Candidate "balanced": convert every kind of risk into minutes of driving and pick the lowest total.
    cost = drive minutes + 60 * No Travel miles + 8 * Severe miles + 2 * High miles
"""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable

from django.conf import settings

from . import telemetry
from .planner import Evaluated

logger = logging.getLogger(__name__)

PENALTY_MIN_PER_MILE = {"no_travel": 60.0, "severe": 8.0, "high": 2.0}


def balanced_cost(ev: Evaluated) -> float:
    return (
        ev.route.duration_s / 60
        + PENALTY_MIN_PER_MILE["no_travel"] * ev.no_travel_miles
        + PENALTY_MIN_PER_MILE["severe"] * ev.severe_miles
        + PENALTY_MIN_PER_MILE["high"] * ev.high_miles
    )


POLICIES: dict[str, Callable[[Evaluated], object]] = {
    "control": lambda ev: ev.sort_key,
    "balanced": balanced_cost,
}


def compare(evs: list[Evaluated]) -> dict:
    """Pick a winner under every policy and summarise the disagreement."""
    winners = {name: min(evs, key=key) for name, key in POLICIES.items()}
    control, cand = winners["control"], winners["balanced"]
    return {
        "control": control.label,
        "candidate": cand.label,
        "agree": control is cand,
        "extra_minutes": round((cand.route.duration_s - control.route.duration_s) / 60),
        "severe_miles_delta": round(cand.severe_miles - control.severe_miles, 1),
        "high_miles_delta": round(cand.high_miles - control.high_miles, 1),
        "no_travel_miles_delta": round(cand.no_travel_miles - control.no_travel_miles, 1),
        "candidate_no_travel": round(cand.no_travel_miles, 1),
    }


def run(evs: list[Evaluated], request_payload: dict, latency_ms: float) -> None:
    """Evaluate and log. Pure CPU on data already in memory, and wrapped so it can never fail a request."""
    if not settings.SHADOW_ENABLED:
        return
    try:
        digest = hashlib.sha1(repr(sorted(request_payload.items())).encode()).hexdigest()[:12]
        telemetry.record("shadow", {"request": digest, "latency_ms": round(latency_ms), **compare(evs), **request_payload})
    except Exception:  # noqa: BLE001 - shadow code is observational only
        logger.exception("shadow evaluation failed")
