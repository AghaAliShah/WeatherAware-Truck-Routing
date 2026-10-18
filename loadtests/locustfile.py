"""Locust load test for the Weather-Aware Truck Routing API.

Run against a local stack that uses the mock upstreams (never load-test the public OSRM / Open-Meteo):

    python loadtests/mock_upstreams.py &
    OSRM_BASE_URL=http://127.0.0.1:9000 PHOTON_URL=http://127.0.0.1:9000 \
    OPEN_METEO_URL=http://127.0.0.1:9000/v1/forecast \
    API_THROTTLE=100000/min API_THROTTLE_PLAN=100000/min API_THROTTLE_EVENTS=100000/min \
    DJANGO_DEBUG=1 gunicorn config.wsgi --workers 2 --threads 8 --timeout 120   # from backend/

    locust -f loadtests/locustfile.py --host http://127.0.0.1:8000 --headless -u 30 -r 5 -t 1m

Pass/fail gate (exit code 1 on breach), tunable by env: P95_PLAN_MS (default 8000), P95_GEOCODE_MS
(1000), MAX_FAIL_RATIO (0.01).
"""
from __future__ import annotations

import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from locust import HttpUser, between, events, task

sys.path.insert(0, os.path.dirname(__file__))
from trips import make_trip  # noqa: E402

P95_PLAN_MS = float(os.environ.get("P95_PLAN_MS", "8000"))
P95_GEOCODE_MS = float(os.environ.get("P95_GEOCODE_MS", "1000"))
MAX_FAIL_RATIO = float(os.environ.get("MAX_FAIL_RATIO", "0.01"))


class Driver(HttpUser):
    """A dispatcher using the app: type a place, plan a trip, scrub the forecast, click around."""

    wait_time = between(1, 3)

    def on_start(self):
        self.rng = random.Random()
        self.visitor = uuid.uuid4().hex
        self.plan = None

    @task(6)
    def search_place(self):
        q = self.rng.choice(["chi", "den", "mem", "dal", "atl", "sea", "pho", "bos"])
        with self.client.get(f"/api/geocode/?q={q}", name="GET /api/geocode", catch_response=True) as r:
            if r.status_code != 200 or "results" not in r.json():
                r.failure(f"bad geocode response {r.status_code}")

    @task(3)
    def plan_trip(self):
        trip = make_trip(self.rng)
        with self.client.post("/api/plan/", json=trip, name="POST /api/plan", catch_response=True) as r:
            if r.status_code != 200:
                return r.failure(f"HTTP {r.status_code}: {r.text[:120]}")
            body = r.json()
            routes = body.get("routes", [])
            if len(routes) < 1 or not any(x["recommended"] for x in routes):
                return r.failure("no recommended route")
            if sorted(x["rank"] for x in routes) != list(range(1, len(routes) + 1)):
                return r.failure("ranks are not 1..n")
            if any(len(c["series"]) != 49 for x in routes for c in x["checkpoints"]):
                return r.failure("checkpoint series is not 49 hours")
            self.plan = body

    @task(2)
    def heatmap(self):
        if not self.plan:
            return
        lines = [[[p[0], p[1]] for p in r["geometry"][:: max(1, len(r["geometry"]) // 300)]] for r in self.plan["routes"]]
        payload = {"polylines": lines, "start": self.plan["departure"], "load_lb": self.plan["load_lb"]}
        with self.client.post("/api/heatmap/", json=payload, name="POST /api/heatmap", catch_response=True) as r:
            if r.status_code != 200:
                return r.failure(f"HTTP {r.status_code}")
            body = r.json()
            if len(body["hours"]) != 49 or any(len(h) != len(body["points"]) for h in body["hours"]):
                r.failure("malformed heatmap grid")

    @task(4)
    def track_event(self):
        payload = {
            "visitor": self.visitor,
            "experiment": "why_default",
            "variant": self.rng.choice(["control", "open"]),
            "event": self.rng.choice(["exposure", "route_selected", "checkpoint_opened", "slider_used"]),
        }
        self.client.post("/api/events/", json=payload, name="POST /api/events")

    @task(1)
    def health(self):
        self.client.get("/api/health/", name="GET /api/health")

    @task(1)
    def static_index(self):
        self.client.get("/", name="GET / (SPA)")


@events.quitting.add_listener
def enforce_slos(environment, **_):
    stats = environment.stats
    problems = []
    if stats.total.fail_ratio > MAX_FAIL_RATIO:
        problems.append(f"failure ratio {stats.total.fail_ratio:.2%} > {MAX_FAIL_RATIO:.2%}")
    for name, limit in (("POST /api/plan", P95_PLAN_MS), ("GET /api/geocode", P95_GEOCODE_MS)):
        entry = stats.entries.get((name, "POST" if name.startswith("POST") else "GET"))
        if entry and entry.num_requests and entry.get_response_time_percentile(0.95) > limit:
            problems.append(f"{name} p95 {entry.get_response_time_percentile(0.95):.0f} ms > {limit:.0f} ms")
    if problems:
        print("SLO BREACH: " + "; ".join(problems))
        environment.process_exit_code = 1
    else:
        print("SLOs met.")
