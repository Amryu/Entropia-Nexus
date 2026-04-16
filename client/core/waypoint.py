"""Waypoint sanitization and formatting helpers.

Mirrors `nexus/src/lib/mapUtil.js` getWaypoint/sanitize* functions so
client-side waypoint construction follows the same rules:

- Planet name uses TechnicalName (game requires it)
- Waypoint name is stripped of commas, trimmed, and capped at 50 chars
- Altitude defaults to 100 when null/missing/zero
"""

from __future__ import annotations

from typing import Any

WAYPOINT_NAME_MAX = 50
DEFAULT_ALTITUDE = 100


def planet_technical_name(planet: Any) -> str:
    """Extract TechnicalName from a planet dict, falling back to Name. Accepts strings unchanged."""
    if planet is None:
        return ""
    if isinstance(planet, str):
        return planet
    if isinstance(planet, dict):
        props = planet.get("Properties") or {}
        return props.get("TechnicalName") or planet.get("Name") or ""
    return ""


def sanitize_waypoint_name(name: Any) -> str:
    if name is None:
        return ""
    return str(name).replace(",", "").strip()[:WAYPOINT_NAME_MAX]


def sanitize_waypoint_altitude(alt: Any) -> float:
    if alt is None:
        return float(DEFAULT_ALTITUDE)
    try:
        n = float(alt)
    except (TypeError, ValueError):
        return float(DEFAULT_ALTITUDE)
    if n == 0:
        return float(DEFAULT_ALTITUDE)
    return n


def format_waypoint(planet: Any, lon: Any, lat: Any, alt: Any, name: Any) -> str:
    """Build a sanitized `/wp` waypoint string."""
    p = planet_technical_name(planet)
    try:
        x = float(lon)
        y = float(lat)
    except (TypeError, ValueError):
        x = 0.0
        y = 0.0
    z = sanitize_waypoint_altitude(alt)
    clean = sanitize_waypoint_name(name)
    return f"/wp [{p}, {x:.0f}, {y:.0f}, {z:.0f}, {clean}]"
