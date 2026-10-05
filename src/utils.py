"""Pure-Python helpers shared by ArcPy modules."""

from __future__ import annotations

import math
import re
from pathlib import Path


FEET_TO_METERS = 0.3048
MILES_TO_METERS = 1609.344


def safe_name(value: object, max_length: int = 48) -> str:
    """Return a filesystem/geodatabase-friendly name."""
    text = str(value).strip()
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "item"
    if text[0].isdigit():
        text = f"id_{text}"
    return text[:max_length]


def height_to_meters(value: float, units: str) -> float:
    """Convert a tower/structure height to meters."""
    unit = units.strip().lower()
    if unit in {"m", "meter", "meters", "metre", "metres"}:
        return float(value)
    if unit in {"ft", "foot", "feet"}:
        return float(value) * FEET_TO_METERS
    raise ValueError(f"Unsupported height units: {units}")


def linear_unit_to_meters(value: float, units: str) -> float:
    """Convert common linear units to meters."""
    unit = units.strip().lower()
    if unit in {"m", "meter", "meters", "metre", "metres"}:
        return float(value)
    if unit in {"ft", "foot", "feet"}:
        return float(value) * FEET_TO_METERS
    if unit in {"mi", "mile", "miles"}:
        return float(value) * MILES_TO_METERS
    if unit in {"km", "kilometer", "kilometers", "kilometre", "kilometres"}:
        return float(value) * 1000.0
    raise ValueError(f"Unsupported linear units: {units}")


def tile_ranges(minimum: float, maximum: float, tile_span: float):
    """Yield non-overlapping [start, end] ranges covering an interval."""
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum")
    if tile_span <= 0:
        raise ValueError("tile_span must be positive")
    start = minimum
    while start < maximum:
        end = min(start + tile_span, maximum)
        yield start, end
        start = end


def estimate_tile_count(width: float, height: float, cell_size: float, max_pixels: int) -> int:
    """Return number of service tiles required for a raster request."""
    if min(width, height, cell_size, max_pixels) <= 0:
        raise ValueError("width, height, cell_size and max_pixels must be positive")
    span = cell_size * max_pixels
    return math.ceil(width / span) * math.ceil(height / span)


def ensure_parent(path: str | Path) -> Path:
    """Create the parent directory for a path and return the Path object."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
