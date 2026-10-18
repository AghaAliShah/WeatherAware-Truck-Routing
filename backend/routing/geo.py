"""Small geodesy helpers (no third-party deps)."""
from __future__ import annotations

import math
from bisect import bisect_right

EARTH_RADIUS_MI = 3958.7613
METERS_PER_MILE = 1609.344

Point = tuple[float, float]  # (lat, lon)


def haversine_mi(a: Point, b: Point) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def cumulative_miles(points: list[Point]) -> list[float]:
    out = [0.0]
    for i in range(1, len(points)):
        out.append(out[-1] + haversine_mi(points[i - 1], points[i]))
    return out


def interpolate_along(cum: list[float], values: list[float], at: float) -> float:
    """Linear interpolation of `values` (aligned with `cum`) at distance `at`."""
    if at <= cum[0]:
        return values[0]
    if at >= cum[-1]:
        return values[-1]
    i = bisect_right(cum, at)
    span = cum[i] - cum[i - 1]
    t = 0.0 if span == 0 else (at - cum[i - 1]) / span
    return values[i - 1] + t * (values[i] - values[i - 1])


def offset_point(origin: Point, bearing: float, distance_mi: float) -> Point:
    lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
    brg = math.radians(bearing)
    d = distance_mi / EARTH_RADIUS_MI
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brg))
    lon2 = lon1 + math.atan2(
        math.sin(brg) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2)
    )
    return (math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)


def bearing_deg(a: Point, b: Point) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def simplify_indices(points: list[Point], tolerance_deg: float) -> list[int]:
    """Iterative Ramer-Douglas-Peucker; returns indices of retained points
    (planar approximation, fine at display tolerances)."""
    n = len(points)
    if n <= 2:
        return list(range(n))
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        (y1, x1), (y2, x2) = points[lo], points[hi]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, best_i = -1.0, -1
        for i in range(lo + 1, hi):
            y0, x0 = points[i]
            if norm == 0:
                d = math.hypot(x0 - x1, y0 - y1)
            else:
                d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm
            if d > best:
                best, best_i = d, i
        if best > tolerance_deg:
            keep[best_i] = True
            stack.append((lo, best_i))
            stack.append((best_i, hi))
    return [i for i, k in enumerate(keep) if k]


def route_overlap(a: list[Point], b: list[Point], threshold_mi: float = 1.0, samples: int = 60) -> float:
    """Fraction of ~`samples` evenly spaced points of `a` lying within
    `threshold_mi` of (a thinned copy of) polyline `b`."""
    if not a or not b:
        return 0.0
    b_pts = b[:: max(1, len(b) // 600)] + [b[-1]]
    picks = a[:: max(1, len(a) // samples)]
    hits = sum(1 for p in picks if any(haversine_mi(p, q) <= threshold_mi for q in b_pts))
    return hits / len(picks)
