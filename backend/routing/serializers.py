from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

MAX_LOAD_LB = 150_000


class LocationSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class DepartureField(serializers.DateTimeField):
    """ISO-8601 datetime; naive values are interpreted as UTC. Must fall within
    a window the weather API can serve (recent past to 10 days ahead)."""

    def to_internal_value(self, value):
        dt = super().to_internal_value(value)
        now = timezone.now()
        if dt < now - timedelta(hours=24) or dt > now + timedelta(days=10):
            raise serializers.ValidationError("Departure must be within the past 24 hours and the next 10 days.")
        return dt


class PlanSerializer(serializers.Serializer):
    origin = LocationSerializer()
    destination = LocationSerializer()
    departure = DepartureField()
    load_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB)
    interval_mi = serializers.ChoiceField(choices=[10, 25, 50], required=False, allow_null=True, default=None)


class HeatmapSerializer(serializers.Serializer):
    polylines = serializers.ListField(
        child=serializers.ListField(
            child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=3),
            min_length=2,
            max_length=2500,
        ),
        min_length=1,
        max_length=3,
    )
    start = DepartureField()
    load_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB)

    def validate_polylines(self, lines):
        for line in lines:
            for p in line:
                if not (-90 <= p[0] <= 90 and -180 <= p[1] <= 180):
                    raise serializers.ValidationError("Coordinate out of range.")
        return lines


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=3, max_length=200)


# Experiments the client may report on. New experiments must be registered here, which keeps the
# endpoint from becoming an open-ended logging sink.
EXPERIMENTS = {"why_default": {"control", "open"}}
EVENT_NAMES = {"exposure", "plan_submitted", "route_selected", "checkpoint_opened", "why_toggled", "slider_used"}


class EventSerializer(serializers.Serializer):
    visitor = serializers.RegexField(r"^[A-Za-z0-9_-]{8,64}$")
    experiment = serializers.ChoiceField(choices=sorted(EXPERIMENTS))
    variant = serializers.CharField(max_length=20)
    event = serializers.ChoiceField(choices=sorted(EVENT_NAMES))

    def validate(self, attrs):
        if attrs["variant"] not in EXPERIMENTS[attrs["experiment"]]:
            raise serializers.ValidationError({"variant": "Unknown variant for this experiment."})
        return attrs
