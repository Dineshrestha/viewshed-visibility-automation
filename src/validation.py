"""Preflight QA/QC checks."""

from __future__ import annotations

from collections import Counter

import arcpy


VALID_EXTENSION_STATES = {"Available", "CheckedOut", "AlreadyInitialized"}


def _field_names(dataset: str) -> set[str]:
    return {field.name for field in arcpy.ListFields(dataset)}


def _check_projected(dataset: str, label: str, qa: list[dict]) -> bool:
    sr = arcpy.Describe(dataset).spatialReference
    ok = bool(sr and sr.type == "Projected")
    qa.append(
        {
            "Level": "ERROR" if not ok else "INFO",
            "Check": f"{label} projected CRS",
            "Result": "PASS" if ok else "FAIL",
            "Message": sr.name if sr else "No spatial reference",
        }
    )
    return ok


def _check_id_field(dataset: str, field_name: str, label: str, qa: list[dict]) -> bool:
    fields = _field_names(dataset)
    if field_name not in fields:
        qa.append(
            {
                "Level": "ERROR",
                "Check": f"{label} ID field",
                "Result": "FAIL",
                "Message": f"Missing field: {field_name}",
            }
        )
        return False

    values = []
    null_count = 0
    with arcpy.da.SearchCursor(dataset, [field_name]) as cursor:
        for (value,) in cursor:
            if value is None or not str(value).strip():
                null_count += 1
            else:
                values.append(str(value).strip())
    duplicate_count = sum(count - 1 for count in Counter(values).values() if count > 1)
    ok = null_count == 0 and duplicate_count == 0
    qa.append(
        {
            "Level": "ERROR" if not ok else "INFO",
            "Check": f"{label} IDs unique/non-null",
            "Result": "PASS" if ok else "FAIL",
            "Message": f"null={null_count}; duplicates={duplicate_count}",
        }
    )
    return ok


def run_preflight(
    site_layers: list[tuple[str, str]],
    site_id_field: str,
    towers: str,
    tower_id_field: str,
    tower_height_field: str,
    dem: str,
) -> tuple[bool, list[dict]]:
    """Validate datasets before a long batch starts."""
    qa: list[dict] = []
    valid = True

    spatial_status = arcpy.CheckExtension("Spatial")
    three_d_status = arcpy.CheckExtension("3D")
    extension_ok = (
        spatial_status in VALID_EXTENSION_STATES
        or three_d_status in VALID_EXTENSION_STATES
    )
    qa.append(
        {
            "Level": "ERROR" if not extension_ok else "INFO",
            "Check": "Viewshed extension license",
            "Result": "PASS" if extension_ok else "FAIL",
            "Message": (
                f"Spatial Analyst={spatial_status}; "
                f"3D Analyst={three_d_status}; requires either one"
            ),
        }
    )
    valid &= extension_ok

    all_site_ids = []
    for dataset, geom_label in site_layers:
        if not dataset:
            continue
        exists = arcpy.Exists(dataset)
        qa.append(
            {
                "Level": "ERROR" if not exists else "INFO",
                "Check": f"{geom_label} sites exist",
                "Result": "PASS" if exists else "FAIL",
                "Message": str(dataset),
            }
        )
        valid &= exists
        if exists:
            valid &= _check_projected(dataset, f"{geom_label} sites", qa)
            valid &= _check_id_field(dataset, site_id_field, f"{geom_label} sites", qa)
            if site_id_field in _field_names(dataset):
                with arcpy.da.SearchCursor(dataset, [site_id_field]) as cursor:
                    for (value,) in cursor:
                        if value is not None and str(value).strip():
                            all_site_ids.append(str(value).strip())

    cross_duplicates = sum(
        count - 1 for count in Counter(all_site_ids).values() if count > 1
    )
    cross_ok = cross_duplicates == 0
    qa.append(
        {
            "Level": "ERROR" if not cross_ok else "INFO",
            "Check": "Site IDs unique across geometry layers",
            "Result": "PASS" if cross_ok else "FAIL",
            "Message": f"sites={len(all_site_ids)}; cross-layer duplicates={cross_duplicates}",
        }
    )
    valid &= cross_ok

    tower_exists = arcpy.Exists(towers)
    qa.append(
        {
            "Level": "ERROR" if not tower_exists else "INFO",
            "Check": "Tower layer exists",
            "Result": "PASS" if tower_exists else "FAIL",
            "Message": str(towers),
        }
    )
    valid &= tower_exists
    if tower_exists:
        valid &= _check_projected(towers, "Towers", qa)
        fields = _field_names(towers)
        for required in (tower_id_field, tower_height_field):
            ok = required in fields
            qa.append(
                {
                    "Level": "ERROR" if not ok else "INFO",
                    "Check": f"Tower field {required}",
                    "Result": "PASS" if ok else "FAIL",
                    "Message": required,
                }
            )
            valid &= ok
        if tower_id_field in fields:
            valid &= _check_id_field(towers, tower_id_field, "Towers", qa)
        if tower_height_field in fields:
            bad_height = 0
            with arcpy.da.SearchCursor(towers, [tower_height_field]) as cursor:
                for (height,) in cursor:
                    if height is None or float(height) <= 0:
                        bad_height += 1
            ok = bad_height == 0
            qa.append(
                {
                    "Level": "ERROR" if not ok else "INFO",
                    "Check": "Tower heights positive/non-null",
                    "Result": "PASS" if ok else "FAIL",
                    "Message": f"invalid={bad_height}",
                }
            )
            valid &= ok

    dem_exists = arcpy.Exists(dem)
    qa.append(
        {
            "Level": "ERROR" if not dem_exists else "INFO",
            "Check": "DEM exists",
            "Result": "PASS" if dem_exists else "FAIL",
            "Message": str(dem),
        }
    )
    valid &= dem_exists
    if dem_exists:
        valid &= _check_projected(dem, "DEM", qa)
        cell_x = float(arcpy.management.GetRasterProperties(dem, "CELLSIZEX").getOutput(0))
        cell_y = float(arcpy.management.GetRasterProperties(dem, "CELLSIZEY").getOutput(0))
        qa.append(
            {
                "Level": "INFO",
                "Check": "DEM cell size",
                "Result": "PASS",
                "Message": f"{cell_x:g} x {cell_y:g} map units",
            }
        )

    return bool(valid), qa
