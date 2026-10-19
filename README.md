# Weather-Aware Truck Routing

A React + Django app that helps a truck driver pick the safest route for a trip, based on forecast
weather **at the time the truck actually reaches each point**, the load weight, and travel time.

Enter origin, destination, departure time and load weight. The app

1. generates **3 driving routes** (OSRM),
2. samples weather at checkpoints every **10 / 25 / 50 miles**, using the truck's **ETA at each checkpoint** (Open-Meteo hourly forecast),
3. classifies each checkpoint with the assessment's **risk table and load rules**,
4. **recommends** a route (fewest Severe miles → fewest High miles → lowest average risk → shortest time),
5. shows every route, checkpoint, risk level, ETA and summary on a full-screen map, plus a **weather heatmap with a 0–48 h forecast slider**.

### Using the map

* The floating trip panel holds the form, the recommendation (with a "Why this route?" criteria table) and the three route cards; hover a card to highlight its route, click to select it.
* The selected route is drawn in risk-coloured segments with a checkpoint dot at every sample point; a truck marker per route shows where each truck is at the slider time.
* Click a checkpoint (map dot, chart bar or table row) for a detail card: conditions at ETA vs at the slider hour, the reasons for the risk level, and a 48 h timeline for that spot.
* The forecast bar scrubs 0-48 h after departure and animates the weather surface. **At ETA** shows the official risk (forecast when the truck arrives); **At forecast time** recolours every checkpoint and route segment to the conditions at the slider hour. Moving the slider switches to the snapshot automatically.
* Keyboard: arrow keys on the risk chart move between checkpoints, Enter opens one, Esc closes the card.

No API keys are required: OSRM (routing), Nominatim/OpenStreetMap (geocoding) and Open-Meteo (weather) are all key-less.

## Run locally

Prerequisites: Python 3.12+, Node 20+.

```bash
# 1. API
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
DJANGO_DEBUG=1 python manage.py runserver               # http://127.0.0.1:8000

# 2. UI (second terminal)
cd frontend
npm install
npm run dev                                             # http://localhost:5173 (proxies /api to :8000)
```

Tests: `cd backend && DJANGO_DEBUG=1 python manage.py test routing` (risk table, load rules, ETA/weather
alignment, mile attribution, ranking, geometry).

## Deploy to Vercel (free, no Docker)

Uses [Vercel Services](https://vercel.com/docs/services) (Beta, available on all plans): one project, two
independently built services on a shared domain. `vercel.json` is the whole configuration:

```json
{
  "services": { "web": { "root": "frontend/" }, "api": { "root": "backend/" } },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "api" } },
    { "source": "/(.*)", "destination": { "service": "web" } }
  ]
}
```

* **`web`**: the Vite/React app, built to static files and served from Vercel's CDN.
* **`api`**: the Django app. Vercel detects `manage.py`, reads `WSGI_APPLICATION` from the settings and runs it as a
  single Python Vercel Function ([Django on Vercel](https://vercel.com/docs/frameworks/full-stack/django)).
  The Python version comes from `backend/.python-version` and dependencies from `backend/requirements.txt`.

Steps: push to GitHub, then in Vercel choose **Add New → Project**, import the repo, leave the root directory as
the repo root, and deploy. No environment variables are required (an ephemeral Django key is generated at boot).
Optional: `OSRM_BASE_URL`, `CONTACT_EMAIL`, `API_THROTTLE_PLAN`, `SHADOW_ENABLED`, `EVENTS_ENABLED`.

What the Vercel docs say about the points that mattered for this app (checked against the docs, not yet against a live deploy):

* **Request path:** a service receives the *original* path, so `GET /api/plan/` reaches Django as `/api/plan/` and
  `backend/routing/urls.py` needs no changes ([Services routing](https://vercel.com/docs/services/routing)).
* **Duration:** with Fluid compute (on by default) a Hobby function runs up to 300 s, which covers the slowest plan
  requests (about 60 s when the public routing server is slow) ([Limits](https://vercel.com/docs/functions/limitations)).
* **Payload limit:** 4.5 MB per request or response; a plan response is about 55 kB.
* **Filesystem:** read-only except `/tmp`, so telemetry files go to `/tmp` (the same records are in the function logs).
* **Caveats:** Services is a Beta feature. Caches and throttles live in each function instance and reset on cold starts.

The same code also runs anywhere Docker does: `docker build -t truck-routing . && docker run -p 7860:7860 truck-routing`
(`render.yaml` is a ready Render blueprint).

## Pre-deployment testing

| Test | What it proves | Command |
| --- | --- | --- |
| Unit tests | risk rules, ETA/weather alignment, ranking, API contract, experiments | `cd backend && DJANGO_DEBUG=1 python manage.py test routing` |
| Load test (Locust) | latency and error rate under concurrent users, with SLO gate | see below |
| Shadow test | a candidate ranking/deployment is safe on real requests before it serves anyone | `tools/shadow_report.py`, `tools/shadow_replay.py` |
| A/B test | a UI change measurably helps users | `tools/ab_report.py` |
| Stats self-test | the report maths matches hand-computed values | `cd tools && python -m unittest test_stats` |

### Load test with Locust

Never load-test the public OSRM / Open-Meteo / Photon servers. `loadtests/mock_upstreams.py` is a stand-in
for all three (deterministic weather with storms, optional `MOCK_LATENCY_MS`), so the test exercises *this*
app's code and concurrency.

```bash
pip install -r loadtests/requirements.txt
python loadtests/mock_upstreams.py &                          # :9000, MOCK_LATENCY_MS=400 for realism
cd backend
OSRM_BASE_URL=http://127.0.0.1:9000 PHOTON_URL=http://127.0.0.1:9000 OPEN_METEO_URL=http://127.0.0.1:9000/v1/forecast API_THROTTLE=100000/min API_THROTTLE_PLAN=100000/min API_THROTTLE_EVENTS=100000/min DJANGO_DEBUG=1 python manage.py runserver 8000 --noreload     # use gunicorn on Linux/Docker
locust -f ../loadtests/locustfile.py --host http://127.0.0.1:8000 --headless -u 30 -r 10 -t 1m
```

The user model mixes place search (6), trip planning (3), heatmap (2), A/B events (4), health and the SPA.
It validates response *content* (3 routes, one recommended, ranks 1..n, 49-hour series, heatmap grid shape),
not just status codes. Exit code is 1 when an SLO breaks: `P95_PLAN_MS` (8000), `P95_GEOCODE_MS` (1000),
`MAX_FAIL_RATIO` (0.01). Result of a reference run (30 users, 45 s, 400 ms per upstream call, Windows
dev server): 424 requests, 0 failures, `/api/plan` p50 2.6 s / p95 5.1 s, `/api/geocode` p95 1.0 s.
Use the web UI (`locust -f ...` without `--headless`) for ramp-up and stress exploration. Public
deployments are throttled per client (`API_THROTTLE*`), so test a deployed Space with throttles raised
or from several IPs.

### A/B test: `why_default`

* **Question:** does opening the "Why this route?" criteria table by default make people engage more with the routes?
* **Arms:** `control` (collapsed) vs `open`, 50/50, assigned client-side by hashing a random visitor id
  (stable per visitor, no PII). `?exp_why_default=open` forces a variant for QA and is never tracked. Do Not Track is honoured.
* **Events:** `exposure`, `plan_submitted`, `route_selected`, `checkpoint_opened`, `slider_used`, `why_toggled`,
  validated against a whitelist at `POST /api/events/` and stored in `backend/var/event.jsonl` (also logged to stdout).
* **Primary metric:** share of exposed visitors who open a checkpoint. **Guardrails:** route selection, slider use.
* **Analysis:** `python tools/ab_report.py` gives rates with Wilson CIs, a two-proportion z-test, a sample-ratio-mismatch
  check, the sample size still needed, and a verdict. It refuses to call a result below `--min-per-arm` visitors.

### Shadow tests

1. **In-process (always on, `SHADOW_ENABLED`):** each `/api/plan` also evaluates a *candidate* ranking
   (`balanced`: minutes of driving plus 60 min per No Travel mile, 8 per Severe, 2 per High) and logs both
   choices to `backend/var/shadow.jsonl`. The user only ever sees the spec ranking. `python tools/shadow_report.py`
   reports agreement, the average trade-off when they disagree, and **safety regressions**. On the load-test
   traffic the candidate agreed 93% of the time but picked a route with more No Travel miles in one case, so
   the report says *do not promote*, which is the point of running it in shadow.
2. **Deployment mirror:** `python tools/shadow_replay.py --primary <live> --candidate <staging> -n 50` sends identical
   trips to both deployments and diffs route count, recommendation, ranks and risk metrics (with tolerances for
   forecast refresh). Exit code 1 blocks a release. Verified locally: identical builds PASS; a candidate fed
   a different forecast source FAILS (8/8 trips differ).

## How it works

```
backend/routing/
  risk.py       risk table + load rules (pure, unit-tested)
  planner.py    route generation, checkpoint ETAs, metrics, ranking, heatmap grid
  providers.py  OSRM / Nominatim / Open-Meteo clients, batching and caching
  views.py      /api/geocode, /api/plan, /api/heatmap, /api/health
frontend/src/
  styles/       design tokens (colours, spacing, radii, shadows) + base reset
  lib/          typed API client, risk palette, geometry, forecast helpers
  hooks/        useTripPlanner (plan + heatmap lifecycle), useMediaQuery
  components/ui shared primitives: Tip, Segmented, Skeleton, RiskBadge
  features/     planner (form, search), routes (cards, comparison, states),
                map (Leaflet layers, trucks, canvas weather surface), forecast (slider, checkpoint detail)
```

### Routes

OSRM's `alternatives` are requested first. When fewer than three *distinct* routes come back (common
on corridors with one dominant highway) extra candidates are routed through a waypoint pushed sideways
from the fastest route's midpoint. A candidate is accepted only if it shares < 92 % of its geometry
with an existing route and is no more than 1.6× slower than the fastest. If the road network genuinely
offers fewer than three routes the UI says so rather than inventing one.

### Weather at the right time

Each route carries per-segment durations from OSRM (scaled ×1.15 because OSRM models a car, not a
loaded truck). A checkpoint's ETA = departure + cumulative drive time to that mile. Weather is read
from the hourly forecast **for the hour nearest that ETA**, at the checkpoint's location (snapped to
a 0.05° grid so nearby checkpoints share one forecast and requests are cached for 15 min).

Checkpoint spacing is automatic (≤150 mi → 10 mi, ≤500 mi → 25 mi, otherwise 50 mi) or can be forced
to 10 / 25 / 50. Spacing is widened if a trip would otherwise exceed 150 checkpoints.

### Risk rules and decisions on ambiguous points

The overall level of a checkpoint is the worst of wind / rain / snow, then the load rules escalate it:
≥55 mph → No Travel (any load); 45–54 mph and load > 30,000 lb → No Travel; 35–44 mph and load > 40,000 lb → Severe.

The spec table's ranges touch at their edges, so the boundaries are pinned (and tested):

* **Wind** is lower-inclusive: 25 → Moderate, 35 → High, 45 → Severe, 55 → No Travel.
* **Rain / snow** are upper-inclusive because the spec writes No Travel as strictly `> 1.00` / `> 3.0`:
  rain 0.10 → Moderate, > 0.25 High, > 0.50 Severe, > 1.00 No Travel; snow 0.5 → Moderate, > 1.0 High, > 2.0 Severe, > 3.0 No Travel.
* Wind uses **sustained 10 m wind speed** (not gusts); rain = `rain + showers`; snow = `snowfall`
  (inches of snow per hour). All are hourly values, i.e. in/hr and mph.

### Recommendation

Each checkpoint "owns" the stretch of road halfway to its neighbours; summing those stretches gives
**Severe miles**, **High miles** (exactly High, excluding Severe) and a mile-weighted **average risk**
(Low 0 … No Travel 4). Routes are ordered by `(No Travel miles, Severe miles, High miles, average risk, drive time)`.
No Travel miles come first because such a route cannot legally be driven; if even the best route has
some, the app says no route is safe and suggests delaying. The text under "Recommendation" states the
concrete trade-off versus the fastest route (e.g. *avoids 60 mi of Severe weather … for 35 min more driving*).

### Heatmap

`/api/heatmap` builds a regular grid (≤150 points, ~14 mi spacing, widened for long trips) around all
three routes, fetches 49 hourly forecasts (departure → +48 h) in one batched call and returns a compact
severity value per point per hour (0–100, computed with the same thresholds and load rules, interpolated
between thresholds so the surface is smooth). The browser draws it with a canvas heat layer created
once; moving the slider only swaps its data array, so scrubbing and the play animation stay smooth.
Hour 0 is the departure time.

## Limitations and next steps

* The OSRM demo server is for light use only and models cars; production should self-host OSRM/Valhalla with a truck profile (height/weight restrictions).
* Open-Meteo is a model forecast (~2–11 km grid); hourly data cannot resolve a squall line narrower than that. Forecast reach is ~16 days; checkpoints beyond it use the nearest available hour and are flagged.
* Times are shown in the viewer's browser time zone. No rest-break / hours-of-service modelling.
* Rate limiting and caching are per process (in-memory); use Redis if you scale horizontally.
