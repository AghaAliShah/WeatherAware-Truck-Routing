import unittest

from ab_report import analyse, load  # noqa: F401
from stats import required_sample_per_arm, sample_ratio_mismatch, two_proportion_test, wilson_interval


class StatsTests(unittest.TestCase):
    def test_two_proportion_known_value(self):
        # pooled p = 0.575, se = sqrt(0.575*0.425*0.02) = 0.06991, z = 0.15/0.06991 = 2.1456
        r = two_proportion_test(50, 100, 65, 100)
        self.assertAlmostEqual(r["z"], 2.1456, places=3)
        self.assertAlmostEqual(r["p_value"], 0.0319, places=3)
        self.assertAlmostEqual(r["diff"], 0.15)

    def test_identical_rates_are_not_significant(self):
        self.assertGreater(two_proportion_test(40, 100, 40, 100)["p_value"], 0.99)

    def test_wilson_matches_reference(self):
        lo, hi = wilson_interval(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)
        self.assertEqual(wilson_interval(0, 0), (0.0, 0.0))

    def test_srm_flags_a_lopsided_split(self):
        self.assertGreater(sample_ratio_mismatch(500, 505), 0.5)
        self.assertAlmostEqual(sample_ratio_mismatch(500, 600), 0.0026, places=3)  # chi2 = 9.09
        self.assertLess(sample_ratio_mismatch(500, 650), 0.001)

    def test_required_sample_size_is_in_the_textbook_range(self):
        # baseline 10% -> 12% (20% relative lift) needs about 3,800 per arm
        self.assertTrue(3500 < required_sample_per_arm(0.10, 0.2) < 4100)

    def test_analyse_counts_only_exposed_visitors(self):
        data = {
            "control": {"exposure": {"a", "b"}, "checkpoint_opened": {"a", "zzz"}},  # zzz never exposed
            "open": {"exposure": {"c", "d"}, "checkpoint_opened": {"c", "d"}},
        }
        rep = analyse({k: __import__("collections").defaultdict(set, v) for k, v in data.items()}, "control", "open")
        primary = rep["metrics"][0]
        self.assertEqual(primary["x"], {"control": 1, "open": 2})


if __name__ == "__main__":
    unittest.main()
