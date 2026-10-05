"""Extension-free line-of-sight visibility using a DEM loaded into NumPy.

This engine is intentionally targeted at structure visibility rather than a
full viewshed raster. It determines the minimum target height required for a
clear line of sight from any observer associated with a site.
"""

from __future__ import annotations

import math

import arcpy
import numpy as np

from .utils import height_to_meters

EARTH_RADIUS_M = 6_371_008.8


class DEMGrid:
    """In-memory DEM sampler used by the direct line-of-sight engine."""

    def __init__(self, dem: str, vertical_units: str = "Meters") -> None:
        raster = arcpy.Raster(dem)
        self.extent = raster.extent
        self.cell_width = float(raster.meanCellWidth)
        self.cell_height = float(raster.meanCellHeight)
        self.spatial_reference = arcpy.Describe(dem).spatialReference
        self.meters_per_unit = float(
            getattr(self.spatial_reference, "metersPerUnit", None) or 1.0
        )

        sentinel = -3.402823466e38
        array = arcpy.RasterToNumPyArray(
            raster,
            nodata_to_value=sentinel,
        ).astype("float64", copy=False)
        array[array <= sentinel / 2.0] = np.nan

        unit = vertical_units.strip().lower()
        if unit in {"feet", "foot", "ft"}:
            array *= 0.3048
        elif unit not in {"meters", "meter", "m", "metres", "metre"}:
            raise ValueError(f"Unsupported DEM elevation units: {vertical_units}")

        self.array_m = array
        self.nrows, self.ncols = array.shape
        self.cell_size_m = (
            (abs(self.cell_width) + abs(self.cell_height)) / 2.0
        ) * self.meters_per_unit

    def sample(self, x, y):
        """Nearest-cell sample for scalar or NumPy-array x/y coordinates."""
        xs = np.asarray(x, dtype="float64")
        ys = np.asarray(y, dtype="float64")

        cols = np.floor((xs - self.extent.XMin) / self.cell_width).astype("int64")
        rows_from_bottom = np.floor(
            (ys - self.extent.YMin) / self.cell_height
        ).astype("int64")
        rows = self.nrows - 1 - rows_from_bottom

        output = np.full(xs.shape, np.nan, dtype="float64")
        valid = (
            (cols >= 0)
            & (cols < self.ncols)
            & (rows >= 0)
            & (rows < self.nrows)
        )
        if np.any(valid):
            output[valid] = self.array_m[rows[valid], cols[valid]]

        if output.ndim == 0:
            return float(output)
        return output


def minimum_target_height_m(
    dem_grid: DEMGrid,
    observer_xy: tuple[float, float],
    target_xy: tuple[float, float],
    observer_height_m: float,
    refraction_coefficient: float = 0.13,
    sample_step_m: float | None = None,
) -> float | None:
    """Return minimum target height above ground for a clear line of sight.

    Terrain is sampled at roughly half a DEM cell by default. Earth-curvature
    correction uses an effective Earth radius adjusted by a standard
    atmospheric refraction coefficient. ``None`` means the path contains DEM
    NoData or an endpoint lies outside the DEM.
    """
    ox, oy = map(float, observer_xy)
    tx, ty = map(float, target_xy)

    observer_ground = dem_grid.sample(ox, oy)
    target_ground = dem_grid.sample(tx, ty)
    if math.isnan(observer_ground) or math.isnan(target_ground):
        return None

    dx = tx - ox
    dy = ty - oy
    distance_map_units = math.hypot(dx, dy)
    distance_m = distance_map_units * dem_grid.meters_per_unit
    if distance_m <= 0:
        return 0.0

    step_m = float(sample_step_m or max(dem_grid.cell_size_m / 2.0, 1.0))
    segments = max(2, int(math.ceil(distance_m / step_m)))
    fractions = np.arange(1, segments, dtype="float64") / float(segments)
    if fractions.size == 0:
        return 0.0

    xs = ox + dx * fractions
    ys = oy + dy * fractions
    terrain_m = dem_grid.sample(xs, ys)
    if np.isnan(terrain_m).any():
        return None

    observer_abs_m = observer_ground + float(observer_height_m)

    # Curvature/refraction correction. The intermediate terrain surface bulges
    # above the straight endpoint chord by d(D-d)/(2R_eff).
    k = float(refraction_coefficient)
    if not 0.0 <= k < 1.0:
        raise ValueError("refraction_coefficient must be >= 0 and < 1")
    effective_radius_m = EARTH_RADIUS_M / (1.0 - k)
    d_m = fractions * distance_m
    bulge_m = d_m * (distance_m - d_m) / (2.0 * effective_radius_m)
    corrected_terrain_m = terrain_m + bulge_m

    # At fractional distance t, LOS elevation is:
    # z_obs + t * (z_target - z_obs). Solve for the target elevation needed
    # to clear every sampled terrain cell.
    required_target_abs_m = observer_abs_m + (
        corrected_terrain_m - observer_abs_m
    ) / fractions
    required_height_m = float(np.nanmax(required_target_abs_m) - target_ground)
    return max(0.0, required_height_m)


def evaluate_candidate_towers(
    observer_fc: str,
    candidate_towers: str,
    tower_id_field: str,
    tower_height_field: str,
    tower_height_units: str,
    dem_grid: DEMGrid,
    observer_height_m: float,
    refraction_coefficient: float = 0.13,
) -> list[dict]:
    """Classify candidate towers using the site's full observer set."""
    observers: list[tuple[float, float]] = []
    with arcpy.da.SearchCursor(observer_fc, ["SHAPE@XY"]) as cursor:
        for (xy,) in cursor:
            observers.append((float(xy[0]), float(xy[1])))

    rows: list[dict] = []
    with arcpy.da.SearchCursor(
        candidate_towers,
        [tower_id_field, tower_height_field, "SHAPE@XY"],
    ) as cursor:
        for tower_id, tower_height, target_xy in cursor:
            actual_height_m = height_to_meters(
                float(tower_height),
                tower_height_units,
            )
            required_values: list[float] = []
            for observer_xy in observers:
                required = minimum_target_height_m(
                    dem_grid=dem_grid,
                    observer_xy=observer_xy,
                    target_xy=(float(target_xy[0]), float(target_xy[1])),
                    observer_height_m=float(observer_height_m),
                    refraction_coefficient=refraction_coefficient,
                )
                if required is not None:
                    required_values.append(required)

            if required_values:
                required_agl_m = min(required_values)
                visibility = (
                    "Visible" if actual_height_m >= required_agl_m else "Obscured"
                )
            else:
                required_agl_m = None
                visibility = "NoData"

            rows.append(
                {
                    "Site_ID": "",  # caller fills this consistently with ArcGIS engine
                    "Tower_ID": str(tower_id),
                    "Tower_Height_Input": float(tower_height),
                    "Tower_Height_Units": tower_height_units,
                    "Tower_Height_m": actual_height_m,
                    "Required_AGL_m": required_agl_m,
                    "Visibility": visibility,
                }
            )

    return rows
