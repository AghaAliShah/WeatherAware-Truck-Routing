"""Route generation, checkpoint weather sampling, risk metrics, recommendation
and the forecast heatmap grid. Pure logic apart from the `providers` calls."""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import providers
from .errors import PlanningError, UpstreamError
from .geo import (
    METERS_PER_MILE,
    Point,
    bearing_deg,
    cumulative_miles,
    haversine_mi,
    interpolate_along,
    offset_point,
    route_overlap,
    simplify_indices,
)
from .risk import Risk, assess, severity_score

# OSRM models a car; a loaded tractor-trailer is governed to ~65 mph and slower on
# grades/urban links, so car durations are stretched by this factor.
TRUCK_TIME_FACTOR = 1.15
MAX_ROUTE_MILES = 3000
MAX_CHECKPOINTS = 150
DUPLICATE_OVERLAP = 0.92  # >= this share of shared geometry => same route
ROUTE_LABELS = ("Route A", "Route B", "Route C")
HEATMAP_HOURS = 48


# --------------------------------------------------------------------------- routes
@dataclass
class Route:
    coords: list[Point]
    cum_mi: list[float]
    cum_s: list[float]
    roads: list[str]

    @property
    def distance_mi(self) -> float:
        return self.cum_mi[-1]

    @property
    def duration_s(self) -> float:
        return self.cum_s[-1]

    def point_at(self, mile: float) -> Point:
        return (
            interpolate_along(self.cum_mi, [p[0] for p in self.coords], mile),
            interpolate_along(self.cum_mi, [p[1] for p in self.coords], mile),
        )

    def seconds_at(self, mile: float) -> float:
        return interpolate_along(self.cum_mi, self.cum_s, mile)


def build_route(raw: providers.RawRoute) -> Route:
    if raw.ann_distance_m and raw.ann_duration_s:
        cum_mi, cum_s = [0.0], [0.0]
        for d, t in zip(raw.ann_distance_m, raw.ann_duration_s):
            cum_mi.append(cum_mi[-1] + d / METERS_PER_MILE)
            cum_s.append(cum_s[-1] + t * TRUCK_TIME_FACTOR)
    else:  # fall back to geometry length, constant speed
        geo = cumulative_miles(raw.coords)
        total_mi = raw.distance_m / METERS_PER_MILE
        scale = total_mi / geo[-1] if geo[-1] else 1.0
        cum_mi = [g * scale for g in geo]
        cum_s = [m / total_mi * raw.duration_s * TRUCK_TIME_FACTOR if total_mi else 0.0 for m in cum_mi]
    return Route(raw.coords, cum_mi, cum_s, raw.roads)


def generate_routes(origin: Point, dest: Point) -> list[Route]:
    """Up to three genuinely different driving routes, fastest first.

    OSRM's own alternatives are used first. If it returns fewer than three
    distinct ones (common on corridors dominated by one highway), we route via
    a waypoint pushed sideways off the midpoint of the fastest route."""
    if haversine_mi(origin, dest) < 1.0:
        raise PlanningError("Origin and destination are too close together.")

    found: list[Route] = []

    def add(raw: providers.RawRoute, max_ratio: float | None = None) -> bool:
        route = build_route(raw)
        if found and max_ratio and route.duration_s > found[0].duration_s * max_ratio:
            return False
        if any(route_overlap(route.coords, f.coords) >= DUPLICATE_OVERLAP and
               route_overlap(f.coords, route.coords) >= DUPLICATE_OVERLAP for f in found):
            return False
        found.append(route)
        return True

    for raw in providers.fetch_routes([origin, dest], alternatives=True):
        if len(found) < 3:
            add(raw)

    if found[0].distance_mi > MAX_ROUTE_MILES:
        raise PlanningError(f"Trips longer than {MAX_ROUTE_MILES:,} miles are not supported.")

    if len(found) < 3:
        primary = found[0]
        heading = bearing_deg(origin, dest)
        detour_mi = min(60.0, max(8.0, primary.distance_mi * 0.10))
        vias = []
        for fraction in (0.5, 0.33, 0.67):
            mid = primary.point_at(primary.distance_mi * fraction)
            for side in (+90, -90):
                vias.append(offset_point(mid, (heading + side) % 360, detour_mi))

        def try_via(via: Point):
            try:
                return providers.fetch_routes([origin, via, dest], alternatives=False)[0]
            except (PlanningError, UpstreamError):
                return None  # via point not routable

        # Candidates are independent, so query them concurrently (routing latency dominates).
        with ThreadPoolExecutor(max_workers=3) as pool:
            candidates = list(pool.map(try_via, vias))
        for raw in candidates:
            if raw is not None and len(found) < 3:
                add(raw, max_ratio=1.6)

    found.sort(key=lambda r: r.duration_s)
    return found[:3]


# --------------------------------------------------------------------------- weather sampling
def auto_interval(distance_mi: float) -> int:
    """Checkpoint spacing: dense on short trips, coarser on long ones."""
    if distance_mi <= 150:
        return 10
    if distance_mi <= 500:
        return 25
    return 50


def checkpoint_miles(total_mi: float, interval: int) -> list[float]:
    interval = max(interval, math.ceil(total_mi / (MAX_CHECKPOINTS - 1)))
    miles = [float(m) for m in range(0, int(total_mi), interval)]
    # Avoid a near-duplicate right before the destination.
    if miles and total_mi - miles[-1] < interval * 0.25 and len(miles) > 1:
        miles.pop()
    miles.append(total_mi)
    return miles


def _epoch_hour(dt: datetime) -> int:
    return round(dt.timestamp() / 3600)


@dataclass
class Checkpoint:
    index: int
    mile: float
    lat: float
    lon: float
    eta: datetime
    segment_miles: float = 0.0
    level: Risk = Risk.LOW
    wind_mph: float = 0.0
    rain_in_hr: float = 0.0
    snow_in_hr: float = 0.0
    drivers: list[str] = field(default_factory=list)
    forecast_forced: bool = False  # ETA outside forecast window; nearest hour used
    # Conditions at this location for hours 0..48 after departure: (level, wind, rain, snow)
    series: list[tuple[int, float, float, float]] = field(default_factory=list)


@dataclass
class Evaluated:
    route: Route
    label: str
    checkpoints: list[Checkpoint]
    interval_mi: int
    severe_miles: float = 0.0
    high_miles: float = 0.0
    no_travel_miles: float = 0.0
    avg_risk: float = 0.0
    max_level: Risk = Risk.LOW

    @property
    def sort_key(self) -> tuple:
        """Spec order: fewest Severe miles, fewest High miles, lowest average risk,
        shortest time. No Travel miles come first - such a route is not drivable."""
        return (
            round(self.no_travel_miles, 1),
            round(self.severe_miles, 1),
            round(self.high_miles, 1),
            round(self.avg_risk, 2),
            round(self.route.duration_s / 60),
        )


def plan_checkpoints(route: Route, label: str, departure: datetime, interval: int) -> Evaluated:
    miles = checkpoint_miles(route.distance_mi, interval)
    cps = []
    for i, m in enumerate(miles):
        lat, lon = route.point_at(m)
        cps.append(Checkpoint(i, m, lat, lon, departure + timedelta(seconds=route.seconds_at(m))))
    for i, cp in enumerate(cps):
        lo = 0.0 if i == 0 else (cps[i - 1].mile + cp.mile) / 2
        hi = route.distance_mi if i == len(cps) - 1 else (cp.mile + cps[i + 1].mile) / 2
        cp.segment_miles = hi - lo
    return Evaluated(route=route, label=label, checkpoints=cps, interval_mi=interval)


def forecast_series(
    hourly: providers.Hourly, departure_hour: int, fallback: tuple[float, float, float], load_lb: float
) -> list[tuple[int, float, float, float]]:
    """Risk + conditions at one location for each hour 0..HEATMAP_HOURS after departure
    (drives the forecast slider's checkpoint and route colouring)."""
    out = []
    for h in range(HEATMAP_HOURS + 1):
        w, r, s = hourly.at(departure_hour + h) or fallback
        out.append((int(assess(w, r, s, load_lb).level), round(w, 1), round(r, 2), round(s, 2)))
    return out


def apply_weather(
    ev: Evaluated, wx: dict[Point, providers.Hourly], load_lb: float, departure_hour: int = 0
) -> int:
    """Fill in each checkpoint's weather + risk; returns count of checkpoints whose
    ETA fell outside the forecast window (nearest hour used instead)."""
    forced = 0
    for cp in ev.checkpoints:
        hourly = wx[providers.snap((cp.lat, cp.lon))]
        hour = _epoch_hour(cp.eta)
        sample = hourly.at(hour)
        if sample is None:
            clamped = min(max(hour, hourly.first_hour), hourly.last_hour)
            sample = hourly.at(clamped) or (0.0, 0.0, 0.0)
            cp.forecast_forced = True
            forced += 1
        cp.wind_mph, cp.rain_in_hr, cp.snow_in_hr = sample
        result = assess(cp.wind_mph, cp.rain_in_hr, cp.snow_in_hr, load_lb)
        cp.level, cp.drivers = result.level, result.drivers
        cp.series = forecast_series(hourly, departure_hour, sample, load_lb)

    total = ev.route.distance_mi or 1.0
    ev.severe_miles = sum(c.segment_miles for c in ev.checkpoints if c.level == Risk.SEVERE)
    ev.high_miles = sum(c.segment_miles for c in ev.checkpoints if c.level == Risk.HIGH)
    ev.no_travel_miles = sum(c.segment_miles for c in ev.checkpoints if c.level == Risk.NO_TRAVEL)
    ev.avg_risk = sum(int(c.level) * c.segment_miles for c in ev.checkpoints) / total
    ev.max_level = max(c.level for c in ev.checkpoints)
    return forced


def weather_window(departure: datetime, longest_s: float) -> tuple[str, str]:
    # Cover the whole trip and the 48 h forecast slider, whichever is longer.
    span = max(timedelta(seconds=longest_s) + timedelta(hours=2), timedelta(hours=HEATMAP_HOURS + 2))
    end = departure + span
    return departure.date().isoformat(), end.date().isoformat()


def evaluate_trip(origin: Point, dest: Point, departure: datetime, load_lb: float, interval: int | None):
    """Returns (evaluated routes sorted best-first, notes)."""
    routes = generate_routes(origin, dest)
    notes: list[str] = []
    if len(routes) < 3:
        notes.append(f"Only {len(routes)} distinct driving route(s) exist between these points.")

    chosen = interval or auto_interval(routes[0].distance_mi)
    evs = [plan_checkpoints(r, lbl, departure, chosen) for r, lbl in zip(routes, ROUTE_LABELS)]

    start, end = weather_window(departure, max(r.duration_s for r in routes))
    points = [(c.lat, c.lon) for ev in evs for c in ev.checkpoints]
    wx = providers.fetch_weather(points, start, end)
    dep_hour = _epoch_hour(departure.replace(minute=0, second=0, microsecond=0))
    forced = sum(apply_weather(ev, wx, load_lb, dep_hour) for ev in evs)
    if forced:
        notes.append(
            f"{forced} checkpoint ETA(s) fall outside the available forecast; the nearest forecast hour was used."
        )
    ranked = sorted(evs, key=lambda e: e.sort_key)
    return evs, ranked, notes


def recommendation_text(evs: list[Evaluated], best: Evaluated) -> str:
    fastest = min(evs, key=lambda e: e.route.duration_s)
    if best.no_travel_miles > 0:
        return (
            f"No route is safe at this departure time: even {best.label} crosses "
            f"{best.no_travel_miles:.0f} mi of No Travel weather. Consider delaying departure."
        )
    if best is fastest:
        return f"{best.label} is the fastest route and has the lowest weather risk."

    if fastest.no_travel_miles > 0:
        why = f"avoids {fastest.no_travel_miles:.0f} mi of No Travel weather"
    elif fastest.severe_miles - best.severe_miles >= 0.05:
        why = f"avoids {fastest.severe_miles - best.severe_miles:.0f} mi of Severe weather"
    elif fastest.high_miles - best.high_miles >= 0.05:
        why = f"avoids {fastest.high_miles - best.high_miles:.0f} mi of High-risk weather"
    else:
        why = f"has lower average risk ({best.avg_risk:.2f} vs {fastest.avg_risk:.2f})"
    extra_min = round((best.route.duration_s - fastest.route.duration_s) / 60)
    return f"{best.label} {why} compared with the fastest route ({fastest.label}), for {extra_min} min more driving."


# --------------------------------------------------------------------------- output shaping
def simplified_geometry(route: Route, tolerance_deg: float = 0.001) -> list[list[float]]:
    idx = simplify_indices(route.coords, tolerance_deg)
    return [[round(route.coords[i][0], 5), round(route.coords[i][1], 5), round(route.cum_mi[i], 2)] for i in idx]


# --------------------------------------------------------------------------- heatmap
def corridor_grid(polylines: list[list[Point]], max_points: int = 150) -> tuple[list[Point], float]:
    """Regular lat/lon grid covering a ring around all route polylines.
    Cell size grows until the grid fits `max_points` (keeps the API call small)."""
    lats = [p[0] for line in polylines for p in line]
    lons = [p[1] for line in polylines for p in line]
    mid_lat = (min(lats) + max(lats)) / 2
    lon_scale = max(0.2, math.cos(math.radians(mid_lat)))

    cell = 0.2  # degrees of latitude (~14 mi)
    while True:
        cells: set[tuple[int, int]] = set()
        for line in polylines:
            prev = None
            for lat, lon in line:
                pts = [(lat, lon)]
                if prev:  # densify so a long straight segment leaves no holes
                    gap = max(abs(lat - prev[0]), abs(lon - prev[1]) * lon_scale)
                    n = int(gap / (cell / 2))
                    pts = [(prev[0] + (lat - prev[0]) * k / (n + 1), prev[1] + (lon - prev[1]) * k / (n + 1))
                           for k in range(1, n + 1)] + pts
                for plat, plon in pts:
                    ci, cj = round(plat / cell), round(plon * lon_scale / cell)
                    for di in (-1, 0, 1):
                        for dj in (-1, 0, 1):
                            cells.add((ci + di, cj + dj))
                prev = (lat, lon)
        if len(cells) <= max_points:
            break
        cell *= 1.25
    points = [(round(i * cell, 4), round(j * cell / lon_scale, 4)) for i, j in sorted(cells)]
    return points, cell


def heatmap(polylines: list[list[Point]], start: datetime, load_lb: float) -> dict:
    """Forecast severity (0-100) for each grid point at hours 0..48 after `start`."""
    start_hour = start.replace(minute=0, second=0, microsecond=0)
    points, cell = corridor_grid(polylines)
    end = start_hour + timedelta(hours=HEATMAP_HOURS)
    wx = providers.fetch_weather(points, start_hour.date().isoformat(), end.date().isoformat())
    first = _epoch_hour(start_hour)

    series: list[list[int]] = [[] for _ in range(HEATMAP_HOURS + 1)]
    for p in points:
        hourly = wx[providers.snap(p)]
        for h in range(HEATMAP_HOURS + 1):
            sample = hourly.at(first + h)
            value = 0 if sample is None else round(severity_score(*sample, load_lb) / 4 * 100)
            series[h].append(value)
    return {
        "start": start_hour.isoformat().replace("+00:00", "Z"),
        "cell_deg": round(cell, 3),
        "points": [[lat, lon] for lat, lon in points],
        "hours": series,
    }


def utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)
