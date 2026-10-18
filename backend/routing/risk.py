"""Weather risk classification: the assessment's risk table and load rules.

Boundary convention (the table's ranges overlap at their edges, so we pin it):
  * Wind uses lower-inclusive bands: >=25 Moderate, >=35 High, >=45 Severe,
    >=55 No Travel (the spec states ">=55" explicitly).
  * Rain and snow use upper-inclusive bands, because the spec states No Travel
    as a strict ">1.00" / ">3.0": rain >=0.10 Moderate, >0.25 High, >0.50
    Severe, >1.00 No Travel; snow >=0.5 Moderate, >1.0 High, >2.0 Severe,
    >3.0 No Travel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Risk(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


@dataclass(frozen=True)
class Bands:
    """Thresholds where Moderate / High / Severe / No Travel begin."""

    moderate: float
    high: float
    severe: float
    no_travel: float
    lower_inclusive: bool  # True: a value equal to a threshold belongs to the higher band

    def level(self, value: float) -> Risk:
        edges = (self.moderate, self.high, self.severe, self.no_travel)
        level = Risk.LOW
        for i, edge in enumerate(edges, start=1):
            if self.lower_inclusive:
                hit = value >= edge
            else:
                # First threshold is the start of Moderate (inclusive);
                # the rest are upper bounds of the band below (exclusive).
                hit = value >= edge if i == 1 else value > edge
            if hit:
                level = Risk(i)
        return level

    def severity(self, value: float) -> float:
        """Continuous 0..4 score, linear between thresholds (heatmap intensity)."""
        edges = (0.0, self.moderate, self.high, self.severe, self.no_travel)
        if value <= 0:
            return 0.0
        for i in range(1, len(edges)):
            if value < edges[i]:
                return (i - 1) + (value - edges[i - 1]) / (edges[i] - edges[i - 1])
        return 4.0


WIND = Bands(25, 35, 45, 55, lower_inclusive=True)  # mph
RAIN = Bands(0.10, 0.25, 0.50, 1.00, lower_inclusive=False)  # in/hr
SNOW = Bands(0.5, 1.0, 2.0, 3.0, lower_inclusive=False)  # in/hr

NO_TRAVEL_WIND_MPH = 55
HEAVY_LOAD_LB = 30_000  # 45-54 mph and strictly above this -> No Travel
VERY_HEAVY_LOAD_LB = 40_000  # 35-44 mph and strictly above this -> Severe


@dataclass(frozen=True)
class Assessment:
    level: Risk
    drivers: list[str] = field(default_factory=list)  # human-readable reasons


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> Assessment:
    """Classify one checkpoint: worst of the three conditions, then escalated
    by the load rules."""
    parts = (
        (WIND.level(wind_mph), f"Wind {wind_mph:.0f} mph"),
        (RAIN.level(rain_in_hr), f"Rain {rain_in_hr:.2f} in/hr"),
        (SNOW.level(snow_in_hr), f"Snow {snow_in_hr:.2f} in/hr"),
    )
    level = max(lvl for lvl, _ in parts)
    drivers = [f"{text} ({lvl.label})" for lvl, text in parts if lvl > Risk.LOW]

    if wind_mph >= NO_TRAVEL_WIND_MPH:
        level = Risk.NO_TRAVEL
    elif wind_mph >= WIND.severe and load_lb > HEAVY_LOAD_LB:
        drivers.append(f"Load {load_lb:,.0f} lb exceeds 30,000 lb in 45-54 mph wind (No Travel)")
        level = Risk.NO_TRAVEL
    elif wind_mph >= WIND.high and load_lb > VERY_HEAVY_LOAD_LB:
        if level < Risk.SEVERE:
            drivers.append(f"Load {load_lb:,.0f} lb exceeds 40,000 lb in 35-44 mph wind (Severe)")
        level = max(level, Risk.SEVERE)

    return Assessment(level=Risk(level), drivers=drivers)


def severity_score(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> float:
    """Continuous 0..4 score consistent with `assess`, including load-rule floors."""
    if wind_mph >= NO_TRAVEL_WIND_MPH:
        return 4.0
    if wind_mph >= WIND.severe and load_lb > HEAVY_LOAD_LB:
        return 4.0
    score = max(WIND.severity(wind_mph), RAIN.severity(rain_in_hr), SNOW.severity(snow_in_hr))
    if wind_mph >= WIND.high and load_lb > VERY_HEAVY_LOAD_LB:
        return max(score, 3.0)
    return score
