"""Small, dependency-free statistics helpers shared by the experiment reports."""
from __future__ import annotations

import math


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion (well behaved for small n and extreme rates)."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def two_proportion_test(x1: int, n1: int, x2: int, n2: int) -> dict:
    """Two-sided pooled z-test for p2 - p1, plus an unpooled 95% CI for the difference."""
    if min(n1, n2) == 0:
        return {"diff": 0.0, "z": 0.0, "p_value": 1.0, "ci": (0.0, 0.0)}
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = 0.0 if se_pooled == 0 else (p2 - p1) / se_pooled
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    diff = p2 - p1
    return {"diff": diff, "z": z, "p_value": 2 * (1 - norm_cdf(abs(z))), "ci": (diff - 1.96 * se, diff + 1.96 * se)}


def sample_ratio_mismatch(n_control: int, n_treatment: int) -> float:
    """Chi-square (1 d.o.f.) p-value for a 50/50 split. A tiny p-value means assignment or logging is broken."""
    total = n_control + n_treatment
    if total == 0:
        return 1.0
    expected = total / 2
    chi2 = (n_control - expected) ** 2 / expected + (n_treatment - expected) ** 2 / expected
    return 2 * (1 - norm_cdf(math.sqrt(chi2)))


def required_sample_per_arm(baseline: float, relative_lift: float, alpha_z: float = 1.96, power_z: float = 0.8416) -> int:
    """Visitors per arm to detect a relative lift at 5% significance / 80% power."""
    p1 = baseline
    p2 = min(0.999, baseline * (1 + relative_lift))
    pbar = (p1 + p2) / 2
    num = (alpha_z * math.sqrt(2 * pbar * (1 - pbar)) + power_z * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return math.ceil(num / (p2 - p1) ** 2) if p2 != p1 else 0
