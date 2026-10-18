from django.test import SimpleTestCase

from routing.risk import RAIN, SNOW, WIND, Risk, assess, severity_score


class BandTests(SimpleTestCase):
    def test_wind_bands(self):
        cases = {0: 0, 24.9: 0, 25: 1, 34.9: 1, 35: 2, 44.9: 2, 45: 3, 54.9: 3, 55: 4, 80: 4}
        for mph, expected in cases.items():
            self.assertEqual(WIND.level(mph), Risk(expected), mph)

    def test_rain_bands(self):
        cases = {0.09: 0, 0.10: 1, 0.25: 1, 0.26: 2, 0.50: 2, 0.51: 3, 1.00: 3, 1.01: 4}
        for v, expected in cases.items():
            self.assertEqual(RAIN.level(v), Risk(expected), v)

    def test_snow_bands(self):
        cases = {0.49: 0, 0.5: 1, 1.0: 1, 1.01: 2, 2.0: 2, 2.01: 3, 3.0: 3, 3.01: 4}
        for v, expected in cases.items():
            self.assertEqual(SNOW.level(v), Risk(expected), v)


class LoadRuleTests(SimpleTestCase):
    def test_55_mph_is_no_travel_for_any_load(self):
        self.assertEqual(assess(55, 0, 0, 0).level, Risk.NO_TRAVEL)

    def test_45_to_54_heavy_load_is_no_travel(self):
        self.assertEqual(assess(50, 0, 0, 30_001).level, Risk.NO_TRAVEL)

    def test_45_to_54_at_threshold_load_stays_severe(self):
        self.assertEqual(assess(50, 0, 0, 30_000).level, Risk.SEVERE)

    def test_35_to_44_very_heavy_load_is_severe(self):
        self.assertEqual(assess(40, 0, 0, 40_001).level, Risk.SEVERE)

    def test_35_to_44_at_threshold_load_stays_high(self):
        self.assertEqual(assess(40, 0, 0, 40_000).level, Risk.HIGH)

    def test_load_rule_does_not_downgrade_worse_conditions(self):
        self.assertEqual(assess(40, 0, 3.5, 45_000).level, Risk.NO_TRAVEL)

    def test_load_rule_ignored_below_wind_band(self):
        self.assertEqual(assess(30, 0, 0, 80_000).level, Risk.MODERATE)

    def test_worst_condition_wins(self):
        self.assertEqual(assess(10, 0.3, 0.6, 10_000).level, Risk.HIGH)

    def test_drivers_explain_the_level(self):
        self.assertTrue(any("Load" in d for d in assess(40, 0, 0, 50_000).drivers))


class SeverityTests(SimpleTestCase):
    def test_monotonic_and_bounded(self):
        scores = [severity_score(w, 0, 0, 0) for w in range(0, 70, 5)]
        self.assertEqual(scores, sorted(scores))
        self.assertEqual(scores[0], 0.0)
        self.assertEqual(scores[-1], 4.0)

    def test_load_floor(self):
        self.assertGreaterEqual(severity_score(40, 0, 0, 50_000), 3.0)
        self.assertEqual(severity_score(50, 0, 0, 35_000), 4.0)
