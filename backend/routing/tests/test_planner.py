from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from routing import planner, providers
from routing.geo import cumulative_miles, haversine_mi, simplify_indices
from routing.risk import Risk

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
FIRST_HOUR = int(T0.timestamp() // 3600)


def straight_route(miles=100.0, mph=50.0):
    """A synthetic route running due north."""
    n = 101
    deg = miles / 69.09
    coords = [(40 + deg * i / (n - 1), -90.0) for i in range(n)]
    cum_mi = cumulative_miles(coords)
    cum_s = [m / mph * 3600 for m in cum_mi]
    return planner.Route(coords, cum_mi, cum_s, ["I 1"])


def hourly(wind=0.0, rain=0.0, snow=0.0, hours=48):
    return providers.Hourly(FIRST_HOUR, [wind] * hours, [rain] * hours, [snow] * hours)


class CheckpointTests(SimpleTestCase):
    def test_miles_start_at_origin_end_at_destination(self):
        miles = planner.checkpoint_miles(130.0, 25)
        self.assertEqual(miles, [0, 25, 50, 75, 100, 125, 130.0][:-2] + [130.0])
        self.assertEqual(miles[0], 0)
        self.assertEqual(miles[-1], 130.0)

    def test_short_trailing_checkpoint_is_dropped(self):
        self.assertEqual(planner.checkpoint_miles(101.0, 25), [0, 25, 50, 75, 101.0])

    def test_auto_interval(self):
        self.assertEqual([planner.auto_interval(d) for d in (50, 300, 900)], [10, 25, 50])

    def test_checkpoint_count_is_capped(self):
        self.assertLessEqual(len(planner.checkpoint_miles(3000, 10)), planner.MAX_CHECKPOINTS)

    def test_segments_cover_route_exactly(self):
        ev = planner.plan_checkpoints(straight_route(), "Route A", T0, 25)
        total = sum(c.segment_miles for c in ev.checkpoints)
        self.assertAlmostEqual(total, ev.route.distance_mi, places=6)

    def test_eta_is_departure_plus_travel_time_to_checkpoint(self):
        ev = planner.plan_checkpoints(straight_route(100, mph=50), "Route A", T0, 25)
        self.assertEqual(ev.checkpoints[0].eta, T0)
        hours = (ev.checkpoints[2].eta - T0).total_seconds() / 3600
        self.assertAlmostEqual(hours, 1.0, delta=0.05)


class WeatherAtEtaTests(SimpleTestCase):
    def test_weather_is_sampled_at_each_checkpoints_eta_hour(self):
        ev = planner.plan_checkpoints(straight_route(100, mph=50), "Route A", T0, 25)  # 2 h trip
        wind = [10.0] * 48
        wind[2] = 60.0  # storm exists only at hour +2
        wx = {
            providers.snap((c.lat, c.lon)): providers.Hourly(FIRST_HOUR, wind, [0.0] * 48, [0.0] * 48)
            for c in ev.checkpoints
        }
        planner.apply_weather(ev, wx, load_lb=10_000)
        for c in ev.checkpoints:
            eta_hours = (c.eta - T0).total_seconds() / 3600
            expected = Risk.NO_TRAVEL if round(eta_hours) == 2 else Risk.LOW
            self.assertEqual(c.level, expected, f"mile {c.mile}")
        self.assertEqual(ev.checkpoints[-1].level, Risk.NO_TRAVEL)
        self.assertEqual(ev.checkpoints[0].level, Risk.LOW)

    def test_miles_attribution(self):
        ev = planner.plan_checkpoints(straight_route(100, mph=50), "Route A", T0, 25)
        wx = {providers.snap((c.lat, c.lon)): hourly(wind=50) for c in ev.checkpoints}
        planner.apply_weather(ev, wx, load_lb=10_000)  # Severe everywhere
        self.assertAlmostEqual(ev.severe_miles, ev.route.distance_mi, places=6)
        self.assertEqual(ev.high_miles, 0)
        self.assertAlmostEqual(ev.avg_risk, 3.0)

    def test_series_covers_48_hours_and_follows_the_forecast(self):
        ev = planner.plan_checkpoints(straight_route(100, mph=50), "Route A", T0, 25)
        wind = [10.0] * 60
        wind[5] = 60.0
        wx = {
            providers.snap((c.lat, c.lon)): providers.Hourly(FIRST_HOUR, wind, [0.0] * 60, [0.0] * 60)
            for c in ev.checkpoints
        }
        planner.apply_weather(ev, wx, load_lb=10_000, departure_hour=FIRST_HOUR)
        series = ev.checkpoints[0].series
        self.assertEqual(len(series), planner.HEATMAP_HOURS + 1)
        self.assertEqual(series[5][0], int(Risk.NO_TRAVEL))
        self.assertEqual(series[4][0], int(Risk.LOW))

    def test_forecast_gap_uses_nearest_hour_and_flags(self):
        ev = planner.plan_checkpoints(straight_route(), "Route A", T0 + timedelta(days=5), 25)
        wx = {providers.snap((c.lat, c.lon)): hourly() for c in ev.checkpoints}
        self.assertEqual(planner.apply_weather(ev, wx, 0), len(ev.checkpoints))


class RankingTests(SimpleTestCase):
    def make(self, label, severe=0.0, high=0.0, avg=0.0, minutes=60, no_travel=0.0):
        route = planner.Route([(0, 0), (0, 1)], [0, 50], [0, minutes * 60], [])
        ev = planner.Evaluated(route, label, [], 25)
        ev.severe_miles, ev.high_miles, ev.avg_risk, ev.no_travel_miles = severe, high, avg, no_travel
        return ev

    def ranked(self, *evs):
        return [e.label for e in sorted(evs, key=lambda e: e.sort_key)]

    def test_severe_miles_beat_everything_else(self):
        a = self.make("A", severe=0, high=90, avg=2, minutes=300)
        b = self.make("B", severe=10, high=0, avg=0.1, minutes=30)
        self.assertEqual(self.ranked(b, a), ["A", "B"])

    def test_high_miles_break_severe_tie(self):
        a = self.make("A", high=20)
        b = self.make("B", high=10, minutes=500)
        self.assertEqual(self.ranked(a, b), ["B", "A"])

    def test_avg_risk_then_time(self):
        a = self.make("A", avg=1.0, minutes=100)
        b = self.make("B", avg=0.5, minutes=200)
        c = self.make("C", avg=0.5, minutes=150)
        self.assertEqual(self.ranked(a, b, c), ["C", "B", "A"])

    def test_no_travel_is_worst(self):
        a = self.make("A", no_travel=10, minutes=10)
        b = self.make("B", severe=200, minutes=900)
        self.assertEqual(self.ranked(a, b), ["B", "A"])

    def test_recommendation_text_names_the_tradeoff(self):
        fast = self.make("Route A", severe=40, minutes=100)
        safe = self.make("Route B", severe=0, minutes=130)
        text = planner.recommendation_text([fast, safe], safe)
        self.assertIn("40 mi of Severe", text)
        self.assertIn("30 min", text)


class GeoTests(SimpleTestCase):
    def test_haversine_chicago_to_memphis(self):
        self.assertAlmostEqual(haversine_mi((41.8781, -87.6298), (35.1495, -90.0490)), 482, delta=5)

    def test_simplify_keeps_corners(self):
        pts = [(0, 0), (0, 1), (0, 2), (1, 2)]
        self.assertEqual(simplify_indices(pts, 0.01), [0, 2, 3])


class GridTests(SimpleTestCase):
    def test_grid_is_bounded_and_covers_route(self):
        line = [(40 + i * 0.1, -90.0) for i in range(100)]
        points, cell = planner.corridor_grid([line], max_points=150)
        self.assertLessEqual(len(points), 150)
        for lat, lon in line[::10]:
            self.assertTrue(any(abs(p[0] - lat) <= cell and abs(p[1] - lon) <= cell * 2 for p in points))
