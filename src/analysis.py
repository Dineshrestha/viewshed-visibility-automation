"""Single-site terrain visibility processing."""

from __future__ import annotations

import os
from pathlib import Path

import arcpy

from .utils import height_to_meters, safe_name


def _delete_if_exists(*datasets) -> None:
    for dataset in datasets:
        if dataset and arcpy.Exists(dataset):
            arcpy.management.Delete(dataset)


def _sample_raster_value(raster: str, geometry, raster_sr) -> float | None:
    """Return a raster cell value at a point without requiring Spatial Analyst."""
    point_geom = geometry
    if geometry.spatialReference and raster_sr:
        if geometry.spatialReference.name != raster_sr.name:
            point_geom = geometry.projectAs(raster_sr)
    point = point_geom.firstPoint
    result = arcpy.management.GetCellValue(raster, f"{point.X} {point.Y}")
    raw = str(result.getOutput(0)).strip()
    if not raw or raw.lower() in {"nodata", "no data", "nan", "#"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def select_candidate_towers(
    towers: str,
    site_geometry,
    search_distance: str,
    scratch_gdb: str,
    token: str,
) -> tuple[str, int]:
    """Copy towers within the search distance of the original site geometry."""
    site_fc = os.path.join(scratch_gdb, f"site_{token}")
    candidates = os.path.join(scratch_gdb, f"towers_{token}")
    layer_name = f"towers_lyr_{token}"
    _delete_if_exists(site_fc, candidates, layer_name)

    arcpy.management.CopyFeatures([site_geometry], site_fc)
    arcpy.management.MakeFeatureLayer(towers, layer_name)
    arcpy.management.SelectLayerByLocation(
        layer_name,
        "WITHIN_A_DISTANCE_GEODESIC",
        site_fc,
        search_distance,
        selection_type="NEW_SELECTION",
    )
    count = int(arcpy.management.GetCount(layer_name).getOutput(0))
    if count:
        arcpy.management.CopyFeatures(layer_name, candidates)
    arcpy.management.Delete(layer_name)
    arcpy.management.Delete(site_fc)
    return candidates, count


def run_site_visibility(
    site_id: str,
    site_geometry,
    observer_fc: str,
    towers: str,
    tower_id_field: str,
    tower_height_field: str,
    tower_height_units: str,
    dem_vertical_units: str,
    dem: str,
    observer_height: str,
    search_distance: str,
    scratch_gdb: str,
    save_viewshed: bool = False,
    viewshed_folder: str | None = None,
) -> tuple[list[dict], int]:
    """Run Geodesic Viewshed and classify candidate tower visibility.

    The Geodesic Viewshed AGL raster stores the minimum height above the DEM
    surface required to make each cell visible from at least one observer.
    A tower is classified Visible when tower_height_m >= required_AGL_m.

    Geodesic Viewshed is invoked through the 3D Analyst toolbox because Esri
    licenses the tool for either Spatial Analyst or 3D Analyst. Raster values
    are sampled with Data Management's Get Cell Value tool so the workflow does
    not add a separate Spatial Analyst-only dependency.
    """
    token = safe_name(site_id, 32)
    candidates, candidate_count = select_candidate_towers(
        towers,
        site_geometry,
        search_distance,
        scratch_gdb,
        token,
    )
    if candidate_count == 0:
        return [], 0

    agl = os.path.join(scratch_gdb, f"agl_{token}")
    viewshed_temp = os.path.join(scratch_gdb, f"viewshed_{token}")
    _delete_if_exists(agl, viewshed_temp)

    arcpy.ddd.Viewshed2(
        in_raster=dem,
        in_observer_features=observer_fc,
        out_raster=viewshed_temp,
        out_agl_raster=agl,
        analysis_type="FREQUENCY",
        observer_offset=observer_height,
        outer_radius=search_distance,
        outer_radius_is_3d="GROUND",
        analysis_method="ALL_SIGHTLINES",
    )

    if save_viewshed:
        if not viewshed_folder:
            raise ValueError("viewshed_folder is required when save_viewshed=True")
        Path(viewshed_folder).mkdir(parents=True, exist_ok=True)
        viewshed_path = str(Path(viewshed_folder) / f"viewshed_{token}.tif")
        if arcpy.Exists(viewshed_path):
            arcpy.management.Delete(viewshed_path)
        arcpy.management.CopyRaster(viewshed_temp, viewshed_path)

    dem_sr = arcpy.Describe(agl).spatialReference
    rows: list[dict] = []
    fields = [tower_id_field, tower_height_field, "SHAPE@"]
    with arcpy.da.SearchCursor(candidates, fields) as cursor:
        for tower_id, tower_height, geometry in cursor:
            tower_height_m = height_to_meters(float(tower_height), tower_height_units)
            required_agl = _sample_raster_value(agl, geometry, dem_sr)
            if required_agl is None or required_agl <= -9990:
                required_agl_m = None
                visibility = "NoData"
            else:
                required_agl_m = height_to_meters(required_agl, dem_vertical_units)
                visibility = "Visible" if tower_height_m >= required_agl_m else "Obscured"

            rows.append(
                {
                    "Site_ID": str(site_id),
                    "Tower_ID": str(tower_id),
                    "Tower_Height_Input": float(tower_height),
                    "Tower_Height_Units": tower_height_units,
                    "Tower_Height_m": tower_height_m,
                    "Required_AGL_m": required_agl_m,
                    "Visibility": visibility,
                }
            )

    _delete_if_exists(candidates, agl, viewshed_temp)
    return rows, candidate_count
