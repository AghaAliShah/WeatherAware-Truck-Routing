"""Thin clients for the third-party services (OSRM, Nominatim, Open-Meteo).

All network access lives here so the planning logic stays pure and testable.
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import PlanningError, UpstreamError
from .geo import Point

logger = logging.getLogger(__name__)

_session = requests.Session()
_session.headers["User-Agent"] = settings.USER_AGENT


def _get_json(url: str, params: dict, what: str, retries: int = 1) -> dict | list:
    last = ""
    for attempt in range(retries + 1):
        try:
            resp = _session.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT_S)
        except requests.RequestException as exc:
            last = f"{what} is unreachable ({type(exc).__name__})"
        else:
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    last = f"{what} returned invalid JSON"
            elif resp.status_code == 400 and what == "Routing service":
                raise PlanningError("No drivable route could be found between those locations.")
            else:
                last = f"{what} returned HTTP {resp.status_code}"
        if attempt < retries:
            time.sleep(1.0 * (attempt + 1))
    raise UpstreamError(last)


# --------------------------------------------------------------------------- geocoding
def _short_label(item: dict) -> str:
    """Compact "Name, City, State" label instead of Nominatim's long display_name."""
    addr = item.get("address", {})
    place = next((addr[k] for k in ("city", "town", "village", "hamlet", "municipality", "county") if addr.get(k)), "")
    street = " ".join(x for x in (addr.get("house_number"), addr.get("road")) if x)
    first = item.get("name") or street
    parts = [first, place if first != place else "", addr.get("state", "")]
    seen, out = set(), []
    for p in parts:
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return ", ".join(out) or item["display_name"].split(", ")[0]


def _dedupe(results: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in results:
        k = r["label"].lower()
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def _photon(query: str, limit: int) -> list[dict]:
    """Photon does prefix matching, so it works as search-as-you-type ("memph" -> Memphis)."""
    data = _get_json(
        f"{settings.PHOTON_URL}/api/",
        {"q": query, "limit": limit, "lang": "en", "bbox": "-170,14,-50,72"},
        "Geocoding service",
        retries=0,
    )
    results = []
    for f in data.get("features", []):
        p, (lon, lat) = f["properties"], f["geometry"]["coordinates"]
        street = " ".join(x for x in (p.get("housenumber"), p.get("street")) if x)
        first = p.get("name") or street
        parts = [first, p.get("city") if p.get("city") != first else "", p.get("state", "")]
        label = ", ".join(dict.fromkeys(x for x in parts if x))
        if label:
            results.append({"label": label, "lat": float(lat), "lon": float(lon)})
    return results


def _nominatim(query: str, limit: int) -> list[dict]:
    data = _get_json(
        f"{settings.NOMINATIM_URL}/search",
        {"q": query, "format": "jsonv2", "limit": limit, "countrycodes": "us,ca,mx", "addressdetails": 1, "dedupe": 1},
        "Geocoding service",
        retries=0,
    )
    return [
        {"label": _short_label(i), "lat": float(i["lat"]), "lon": float(i["lon"])} for i in data if "lat" in i and "lon" in i
    ]


def geocode(query: str, limit: int = 5) -> list[dict]:
    query = " ".join(query.lower().split())
    key = "geo:" + hashlib.sha1(query.encode()).hexdigest()
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        results = _photon(query, limit)
    except UpstreamError:
        results = _nominatim(query, limit)  # fallback provider
    results = _dedupe(results)
    cache.set(key, results, 24 * 3600)
    return results


# --------------------------------------------------------------------------- routing
@dataclass
class RawRoute:
    coords: list[Point]  # (lat, lon), full resolution
    ann_distance_m: list[float] | None  # per-segment, len == len(coords) - 1
    ann_duration_s: list[float] | None
    distance_m: float
    duration_s: float
    roads: list[str]  # most-travelled road names, descending distance


def _road_summary(legs: list[dict]) -> list[str]:
    """Most-driven roads. Numbered routes (I 90, US 20) lead; street names only fill gaps."""
    refs: dict[str, float] = defaultdict(float)
    names: dict[str, float] = defaultdict(float)
    for leg in legs:
        for step in leg.get("steps", []):
            dist = step.get("distance", 0.0)
            if step.get("ref"):
                refs[step["ref"].split(";")[0].strip()] += dist
            elif step.get("name"):
                names[step["name"].strip()] += dist
    ranked = [k for k, _ in sorted(refs.items(), key=lambda kv: kv[1], reverse=True)]
    if len(ranked) < 2:
        ranked += [k for k, _ in sorted(names.items(), key=lambda kv: kv[1], reverse=True)]
    return ranked[:3]


def fetch_routes(waypoints: list[Point], alternatives: bool) -> list[RawRoute]:
    """Driving routes through `waypoints` (lat, lon) from OSRM."""
    coord_str = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in waypoints)
    data = _get_json(
        f"{settings.OSRM_BASE_URL}/route/v1/driving/{coord_str}",
        {
            "alternatives": "3" if alternatives else "false",
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "annotations": "distance,duration",
        },
        "Routing service",
    )
    if data.get("code") != "Ok" or not data.get("routes"):
        raise PlanningError("No drivable route could be found between those locations.")

    routes = []
    for r in data["routes"]:
        coords = [(lat, lon) for lon, lat in r["geometry"]["coordinates"]]
        dists: list[float] = []
        durs: list[float] = []
        for leg in r["legs"]:
            ann = leg.get("annotation") or {}
            dists += ann.get("distance", [])
            durs += ann.get("duration", [])
        aligned = len(dists) == len(durs) == len(coords) - 1
        routes.append(
            RawRoute(
                coords=coords,
                ann_distance_m=dists if aligned else None,
                ann_duration_s=durs if aligned else None,
                distance_m=r["distance"],
                duration_s=r["duration"],
                roads=_road_summary(r["legs"]),
            )
        )
    return routes


# --------------------------------------------------------------------------- weather
@dataclass
class Hourly:
    first_hour: int  # epoch hour (unix seconds // 3600) of index 0
    wind_mph: list[float | None]
    rain_in: list[float | None]
    snow_in: list[float | None]

    def at(self, epoch_hour: int) -> tuple[float, float, float] | None:
        """Weather for an epoch hour, or None if outside the loaded window / missing."""
        i = epoch_hour - self.first_hour
        if not 0 <= i < len(self.wind_mph):
            return None
        w, r, s = self.wind_mph[i], self.rain_in[i], self.snow_in[i]
        if w is None or r is None or s is None:
            return None
        return w, r, s

    @property
    def last_hour(self) -> int:
        return self.first_hour + len(self.wind_mph) - 1


SNAP_DEG = 0.05  # ~3.5 mi; the weather model is coarser than this
CHUNK = 20  # locations per Open-Meteo request (request time grows with locations; chunks run in parallel)
CACHE_TTL_S = 15 * 60


def snap(p: Point) -> Point:
    return (round(round(p[0] / SNAP_DEG) * SNAP_DEG, 4), round(round(p[1] / SNAP_DEG) * SNAP_DEG, 4))


def _parse_hourly(block: dict) -> Hourly:
    h = block["hourly"]
    times = h["time"]
    rain = [None if a is None else a + (b or 0.0) for a, b in zip(h["rain"], h["showers"])]
    return Hourly(
        first_hour=times[0] // 3600,
        wind_mph=h["wind_speed_10m"],
        rain_in=rain,
        snow_in=h["snowfall"],
    )


def _fetch_chunk(points: list[Point], start_date: str, end_date: str) -> list[Hourly]:
    data = _get_json(
        settings.OPEN_METEO_URL,
        {
            "latitude": ",".join(f"{p[0]:.4f}" for p in points),
            "longitude": ",".join(f"{p[1]:.4f}" for p in points),
            "hourly": "wind_speed_10m,rain,showers,snowfall",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "start_date": start_date,
            "end_date": end_date,
        },
        "Weather service",
        retries=2,
    )
    blocks = data if isinstance(data, list) else [data]
    if len(blocks) != len(points):
        raise UpstreamError("Weather service returned an unexpected number of locations")
    return [_parse_hourly(b) for b in blocks]


def fetch_weather(points: list[Point], start_date: str, end_date: str) -> dict[Point, Hourly]:
    """Hourly wind / rain / snow for each (snapped, de-duplicated) point.
    Dates are ISO `YYYY-MM-DD` in UTC. Results are cached for 15 minutes."""
    unique = sorted({snap(p) for p in points})
    out: dict[Point, Hourly] = {}
    missing: list[Point] = []
    for p in unique:
        hit = cache.get(f"wx:{p[0]}:{p[1]}:{start_date}:{end_date}")
        if hit is not None:
            out[p] = hit
        else:
            missing.append(p)

    chunks = [missing[i : i + CHUNK] for i in range(0, len(missing), CHUNK)]
    if chunks:
        with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as pool:
            results = list(pool.map(lambda c: _fetch_chunk(c, start_date, end_date), chunks))
        for chunk, hourly in zip(chunks, results):
            for p, hrs in zip(chunk, hourly):
                out[p] = hrs
                cache.set(f"wx:{p[0]}:{p[1]}:{start_date}:{end_date}", hrs, CACHE_TTL_S)
    return out
