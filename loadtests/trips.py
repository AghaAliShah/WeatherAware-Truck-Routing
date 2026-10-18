"""Shared trip fixtures for load, shadow-replay and smoke tests."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

CITIES = {
    "Chicago": (41.8756, -87.6244),
    "Denver": (39.7392, -104.9849),
    "Memphis": (35.1495, -90.0490),
    "Dallas": (32.7767, -96.7970),
    "Atlanta": (33.7490, -84.3880),
    "Seattle": (47.6062, -122.3321),
    "Phoenix": (33.4484, -112.0740),
    "Boston": (42.3601, -71.0589),
    "Kansas City": (39.0997, -94.5786),
    "Minneapolis": (44.9778, -93.2650),
}

LOADS_LB = [8_000, 25_000, 35_000, 42_000, 60_000, 80_000]


def make_trip(rng: random.Random, departure_in_hours: float | None = None) -> dict:
    (o_name, o), (d_name, d) = rng.sample(sorted(CITIES.items()), 2)
    hours = rng.choice([1, 3, 12, 30]) if departure_in_hours is None else departure_in_hours
    departure = datetime.now(timezone.utc) + timedelta(hours=hours)
    return {
        "origin": {"lat": o[0], "lon": o[1], "label": o_name},
        "destination": {"lat": d[0], "lon": d[1], "label": d_name},
        "departure": departure.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "load_lb": rng.choice(LOADS_LB),
        "interval_mi": None,
    }
