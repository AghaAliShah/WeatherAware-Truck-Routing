import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient

from routing import planner, shadow


def make(label, severe=0.0, high=0.0, no_travel=0.0, minutes=60.0, avg=0.0):
    route = planner.Route([(0, 0), (0, 1)], [0, 50], [0, minutes * 60], [])
    ev = planner.Evaluated(route, label, [], 25)
    ev.severe_miles, ev.high_miles, ev.no_travel_miles, ev.avg_risk = severe, high, no_travel, avg
    return ev


class ShadowPolicyTests(SimpleTestCase):
    def test_policies_agree_when_one_route_dominates(self):
        a, b = make("Route A", minutes=100), make("Route B", severe=10, minutes=120)
        result = shadow.compare([a, b])
        self.assertTrue(result["agree"])
        self.assertEqual(result["extra_minutes"], 0)

    def test_balanced_accepts_a_little_high_risk_to_save_a_lot_of_time(self):
        slow_safe = make("Route A", minutes=600)
        fast_risky = make("Route B", high=10, minutes=300)  # control: A (0 High); balanced: B (320 < 600)
        result = shadow.compare([slow_safe, fast_risky])
        self.assertEqual(result["control"], "Route A")
        self.assertEqual(result["candidate"], "Route B")
        self.assertFalse(result["agree"])
        self.assertEqual(result["extra_minutes"], -300)
        self.assertEqual(result["high_miles_delta"], 10)

    def test_no_travel_is_never_traded_for_time(self):
        blocked_fast = make("Route A", no_travel=20, minutes=100)
        safe_slow = make("Route B", minutes=400)
        self.assertEqual(shadow.compare([blocked_fast, safe_slow])["candidate"], "Route B")

    def test_run_never_raises_and_respects_flag(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(TELEMETRY_DIR=tmp, SHADOW_ENABLED=True):
            shadow.run([make("Route A"), make("Route B", minutes=70)], {"load_lb": 1}, 12.0)
            rows = [json.loads(x) for x in Path(tmp, "shadow.jsonl").read_text().splitlines()]
            self.assertEqual(rows[0]["control"], "Route A")
            self.assertIn("latency_ms", rows[0])
        with tempfile.TemporaryDirectory() as tmp, override_settings(TELEMETRY_DIR=tmp, SHADOW_ENABLED=False):
            shadow.run([make("Route A")], {}, 1.0)
            self.assertFalse(Path(tmp, "shadow.jsonl").exists())
        shadow.run([], {}, 1.0)  # malformed input must be swallowed


class EventEndpointTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.valid = {"visitor": "abcdef123456", "experiment": "why_default", "variant": "open", "event": "exposure"}

    def test_valid_event_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(TELEMETRY_DIR=tmp):
            res = self.client.post("/api/events/", self.valid, format="json")
            self.assertEqual(res.status_code, 204)
            row = json.loads(Path(tmp, "event.jsonl").read_text().splitlines()[0])
            self.assertEqual((row["experiment"], row["variant"], row["event"]), ("why_default", "open", "exposure"))

    def test_rejects_unknown_experiment_variant_event_and_bad_visitor(self):
        bad = [
            {**self.valid, "experiment": "nope"},
            {**self.valid, "variant": "zzz"},
            {**self.valid, "event": "drop_table"},
            {**self.valid, "visitor": "<script>alert(1)</script>"},
        ]
        with tempfile.TemporaryDirectory() as tmp, override_settings(TELEMETRY_DIR=tmp):
            for payload in bad:
                self.assertEqual(self.client.post("/api/events/", payload, format="json").status_code, 400, payload)
            self.assertFalse(Path(tmp, "event.jsonl").exists())
