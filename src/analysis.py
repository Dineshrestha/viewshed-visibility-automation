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
    _delete_if_exists(agl)

    viewshed = arcpy.sa.Viewshed2(
        in_raster=dem,
        in_observer_features=observer_fc,
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
        viewshed.save(viewshed_path)

    arcpy.sa.ExtractMultiValuesToPoints(
        candidates,
        [[agl, "AGL_RAW"]],
        "NONE",
    )

    rows: list[dict] = []
    fields = [tower_id_field, tower_height_field, "AGL_RAW"]
    with arcpy.da.SearchCursor(candidates, fields) as cursor:
        for tower_id, tower_height, required_agl in cursor:
            tower_height_m = height_to_meters(float(tower_height), tower_height_units)
            if required_agl is None or float(required_agl) <= -9990:
                required_agl_m = None
                visibility = "NoData"
            else:
                required_agl_m = height_to_meters(float(required_agl), dem_vertical_units)
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

    _delete_if_exists(candidates, agl)
    return rows, candidate_count
