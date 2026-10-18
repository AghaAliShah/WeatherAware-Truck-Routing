import time
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from . import planner, providers, shadow, telemetry
from .serializers import EventSerializer, GeocodeQuerySerializer, HeatmapSerializer, PlanSerializer


class PlanThrottle(AnonRateThrottle):
    scope = "plan"


class EventThrottle(AnonRateThrottle):
    scope = "events"


@api_view(["GET"])
@throttle_classes([])
def health(request):
    return JsonResponse({"status": "ok"})


class GeocodeView(APIView):
    def get(self, request):
        params = GeocodeQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return Response({"results": providers.geocode(params.validated_data["q"].strip())})


class PlanView(APIView):
    throttle_classes = [PlanThrottle]

    def post(self, request):
        s = PlanSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        departure = planner.utc(d["departure"])
        origin = (d["origin"]["lat"], d["origin"]["lon"])
        dest = (d["destination"]["lat"], d["destination"]["lon"])

        started = time.monotonic()
        evs, ranked, notes = planner.evaluate_trip(origin, dest, departure, d["load_lb"], d["interval_mi"])
        best = ranked[0]
        # Shadow: candidate ranking is evaluated and logged; it never changes the response below.
        shadow.run(
            evs,
            {
                "origin": [round(origin[0], 2), round(origin[1], 2)],
                "destination": [round(dest[0], 2), round(dest[1], 2)],
                "load_lb": d["load_lb"],
                "distance_mi": round(evs[0].route.distance_mi),
            },
            (time.monotonic() - started) * 1000,
        )
        fastest = min(evs, key=lambda e: e.route.duration_s)

        def iso(dt):
            return planner.utc(dt).isoformat().replace("+00:00", "Z")

        routes = []
        for ev in evs:
            r = ev.route
            routes.append({
                "id": ev.label.split()[-1].lower(),
                "label": ev.label,
                "summary": "via " + ", ".join(r.roads) if r.roads else "Local roads",
                "distance_mi": round(r.distance_mi, 1),
                "duration_s": round(r.duration_s),
                "arrival": iso(departure + timedelta(seconds=r.duration_s)),
                "rank": ranked.index(ev) + 1,
                "recommended": ev is best,
                "fastest": ev is fastest,
                "metrics": {
                    "no_travel_miles": round(ev.no_travel_miles, 1),
                    "severe_miles": round(ev.severe_miles, 1),
                    "high_miles": round(ev.high_miles, 1),
                    "avg_risk": round(ev.avg_risk, 2),
                    "max_level": ev.max_level.label,
                },
                "geometry": planner.simplified_geometry(r),
                "checkpoints": [{
                    "index": c.index,
                    "mile": round(c.mile, 1),
                    "lat": round(c.lat, 5),
                    "lon": round(c.lon, 5),
                    "eta": iso(c.eta),
                    "segment_miles": round(c.segment_miles, 1),
                    "level": int(c.level),
                    "level_label": c.level.label,
                    "wind_mph": round(c.wind_mph, 1),
                    "rain_in_hr": round(c.rain_in_hr, 2),
                    "snow_in_hr": round(c.snow_in_hr, 2),
                    "drivers": c.drivers,
                    "forecast_forced": c.forecast_forced,
                    "series": [list(row) for row in c.series],
                } for c in ev.checkpoints],
            })
        return Response({
            "departure": iso(departure),
            "load_lb": d["load_lb"],
            "interval_mi": evs[0].interval_mi,
            "recommended_id": routes[evs.index(best)]["id"],
            "recommendation": planner.recommendation_text(evs, best),
            "notes": notes,
            "routes": routes,
        })


class HeatmapView(APIView):
    throttle_classes = [PlanThrottle]

    def post(self, request):
        s = HeatmapSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        lines = [[(p[0], p[1]) for p in line] for line in d["polylines"]]
        return Response(planner.heatmap(lines, planner.utc(d["start"]), d["load_lb"]))


class EventView(APIView):
    """Receives A/B exposure and interaction events from the browser (navigator.sendBeacon)."""

    throttle_classes = [EventThrottle]

    def post(self, request):
        s = EventSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if settings.EVENTS_ENABLED:
            telemetry.record("event", s.validated_data)
        return Response(status=204)
