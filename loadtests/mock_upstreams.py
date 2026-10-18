"""Stand-ins for OSRM, Photon and Open-Meteo so load tests exercise *our* code, not the public APIs.

    python loadtests/mock_upstreams.py            # listens on :9000
    MOCK_LATENCY_MS=600 python loadtests/mock_upstreams.py

Point the app at it with:
    OSRM_BASE_URL=http://127.0.0.1:9000 PHOTON_URL=http://127.0.0.1:9000 \
    OPEN_METEO_URL=http://127.0.0.1:9000/v1/forecast

MOCK_LATENCY_MS adds a fixed delay per request to mimic real network latency (the public OSRM is ~1-4 s).
Weather is deterministic per location/hour and includes storms, so risk logic is exercised.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

LATENCY_S = float(os.environ.get("MOCK_LATENCY_MS", "0")) / 1000
PORT = int(os.environ.get("MOCK_PORT", "9000"))
SEED = os.environ.get("MOCK_WEATHER_SEED", "0")  # change to simulate a different forecast provider
EARTH_M = 6_371_000.0
CITIES = ["Chicago", "Denver", "Memphis", "Dallas", "Atlanta", "Seattle", "Phoenix", "Boston"]


def haversine_m(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH_M * math.asin(math.sqrt(h))


def leg_points(a, b, bulge, n=120):
    """Points a->b with a sinusoidal sideways bulge (degrees) so alternatives genuinely differ."""
    dlat, dlon = b[0] - a[0], b[1] - a[1]
    norm = math.hypot(dlat, dlon) or 1.0
    px, py = -dlon / norm, dlat / norm  # perpendicular
    return [
        (a[0] + dlat * i / n + px * bulge * math.sin(math.pi * i / n), a[1] + dlon * i / n + py * bulge * math.sin(math.pi * i / n))
        for i in range(n + 1)
    ]


def osrm_route(waypoints, bulge):
    legs, geometry = [], []
    for a, b in zip(waypoints, waypoints[1:]):
        pts = leg_points(a, b, bulge)
        dist = [haversine_m(p, q) * 1.15 for p, q in zip(pts, pts[1:])]
        dur = [d / 27.0 for d in dist]  # ~60 mph
        legs.append(
            {
                "annotation": {"distance": dist, "duration": dur},
                "steps": [
                    {"ref": "I 80", "name": "", "distance": sum(dist) * 0.7},
                    {"ref": "", "name": "Main Street", "distance": sum(dist) * 0.3},
                ],
            }
        )
        geometry += pts if not geometry else pts[1:]
    total_d = sum(sum(leg["annotation"]["distance"]) for leg in legs)
    total_t = sum(sum(leg["annotation"]["duration"]) for leg in legs)
    return {
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in geometry]},
        "legs": legs,
        "distance": total_d,
        "duration": total_t,
    }


def hourly_weather(lat, lon, hours):
    """Deterministic pseudo-weather: a slow-moving windy/wet cell keyed by location and hour."""
    seed = int(hashlib.md5(f"{SEED}:{round(lat, 1)}:{round(lon, 1)}".encode()).hexdigest()[:6], 16)
    out_w, out_r, out_s = [], [], []
    for h in range(hours):
        phase = (seed % 97 + h * 1.7) / 9.0
        wind = 12 + 30 * max(0.0, math.sin(phase)) ** 2 + (seed % 7)
        rain = max(0.0, math.sin(phase * 0.8 + 1)) ** 3 * 0.7
        snow = max(0.0, math.sin(phase * 0.5 + 2)) ** 5 * 1.6 if lat > 41 else 0.0
        out_w.append(round(wind, 1))
        out_r.append(round(rain, 3))
        out_s.append(round(snow, 3))
    return out_w, out_r, out_s


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep load-test output readable
        pass

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if LATENCY_S:
            time.sleep(LATENCY_S)
        url = urlsplit(self.path)  # urlsplit keeps ";" (OSRM waypoint separator) in the path
        q = {k: v[0] for k, v in parse_qs(url.query).items()}

        if url.path.startswith("/route/v1/driving/"):
            coords = url.path.rsplit("/", 1)[-1].split(";")
            wps = [(float(c.split(",")[1]), float(c.split(",")[0])) for c in coords]
            if q.get("alternatives") not in (None, "false"):
                routes = [osrm_route(wps, b) for b in (0.0, 0.8, -0.8)]
            else:
                routes = [osrm_route(wps, 0.0)]
            return self._json({"code": "Ok", "routes": routes})

        if url.path == "/api/":  # Photon
            text = q.get("q", "").lower()
            feats = [
                {"geometry": {"coordinates": [-90 + i * 3.1, 33 + i * 1.4]}, "properties": {"name": name, "state": "Testland"}}
                for i, name in enumerate(CITIES)
                if text and name.lower().startswith(text[:3])
            ]
            return self._json({"features": feats[: int(q.get("limit", 5))]})

        if url.path == "/v1/forecast":
            lats, lons = q["latitude"].split(","), q["longitude"].split(",")
            start = datetime.fromisoformat(q["start_date"]).replace(tzinfo=timezone.utc)
            end = datetime.fromisoformat(q["end_date"]).replace(tzinfo=timezone.utc) + timedelta(days=1)
            hours = int((end - start).total_seconds() // 3600)
            times = [int(start.timestamp()) + 3600 * h for h in range(hours)]
            blocks = []
            for la, lo in zip(lats, lons):
                w, r, s = hourly_weather(float(la), float(lo), hours)
                blocks.append({"hourly": {"time": times, "wind_speed_10m": w, "rain": r, "showers": [0.0] * hours, "snowfall": s}})
            return self._json(blocks if len(blocks) > 1 else blocks[0])

        self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    print(f"mock upstreams on :{PORT} (latency {LATENCY_S * 1000:.0f} ms)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
