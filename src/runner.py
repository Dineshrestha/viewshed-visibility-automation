"""Batch orchestration for Viewshed & Visibility Automation."""

from __future__ import annotations

import os
import time
from pathlib import Path

import arcpy

from .analysis import run_site_visibility
from .observers import create_observer_feature_class
from .reporting import write_report
from .status import RunStatus
from .validation import run_preflight


SUMMARY_FIELDS = [
    ("Site_ID", "TEXT", 100),
    ("Geometry_Type", "TEXT", 20),
    ("Observer_Count", "LONG", None),
    ("Candidate_Towers", "LONG", None),
    ("Visible_Towers", "LONG", None),
    ("Obscured_Towers", "LONG", None),
    ("NoData_Towers", "LONG", None),
    ("Status", "TEXT", 20),
    ("Elapsed_Minutes", "DOUBLE", None),
    ("Message", "TEXT", 1000),
]

DETAIL_FIELDS = [
    ("Site_ID", "TEXT", 100),
    ("Tower_ID", "TEXT", 100),
    ("Tower_Height_Input", "DOUBLE", None),
    ("Tower_Height_Units", "TEXT", 20),
    ("Tower_Height_m", "DOUBLE", None),
    ("Required_AGL_m", "DOUBLE", None),
    ("Visibility", "TEXT", 20),
]


def _message(text: str) -> None:
    try:
        arcpy.AddMessage(text)
    except Exception:
        print(text)


def _warning(text: str) -> None:
    try:
        arcpy.AddWarning(text)
    except Exception:
        print(f"WARNING: {text}")


def _checkout_visibility_extension() -> tuple[str, bool]:
    """Checkout Spatial Analyst or 3D Analyst, whichever is available."""
    for extension, label in (("Spatial", "Spatial Analyst"), ("3D", "3D Analyst")):
        status = arcpy.CheckExtension(extension)
        if status == "Available":
            arcpy.CheckOutExtension(extension)
            _message(f"Using {label} license for Geodesic Viewshed.")
            return extension, True
        if status in {"CheckedOut", "AlreadyInitialized"}:
            _message(f"Using existing {label} license for Geodesic Viewshed.")
            return extension, False
    raise RuntimeError(
        "Geodesic Viewshed requires either a Spatial Analyst or 3D Analyst license."
    )


def _create_table(gdb: str, name: str, fields) -> str:
    table = os.path.join(gdb, name)
    if arcpy.Exists(table):
        return table
    arcpy.management.CreateTable(gdb, name)
    for field_name, field_type, length in fields:
        kwargs = {"field_length": length} if length else {}
        arcpy.management.AddField(table, field_name, field_type, **kwargs)
    return table


def _delete_site_rows(table: str, site_id: str) -> None:
    if not arcpy.Exists(table):
        return
    with arcpy.da.UpdateCursor(table, ["Site_ID"]) as cursor:
        for (value,) in cursor:
            if str(value) == str(site_id):
                cursor.deleteRow()


def _insert_dict(table: str, row: dict, columns: list[str]) -> None:
    with arcpy.da.InsertCursor(table, columns) as cursor:
        cursor.insertRow([row.get(column) for column in columns])


def _read_table(table: str, columns: list[str]) -> list[dict]:
    rows = []
    with arcpy.da.SearchCursor(table, columns) as cursor:
        for values in cursor:
            rows.append(dict(zip(columns, values)))
    return rows


def _ensure_observer_output(gdb: str, spatial_reference) -> str:
    output_fc = os.path.join(gdb, "Observers_All")
    if arcpy.Exists(output_fc):
        return output_fc
    arcpy.management.CreateFeatureclass(
        gdb,
        "Observers_All",
        "POINT",
        spatial_reference=spatial_reference,
    )
    arcpy.management.AddField(output_fc, "Site_ID", "TEXT", field_length=100)
    arcpy.management.AddField(output_fc, "Observer_ID", "TEXT", field_length=120)
    arcpy.management.AddField(output_fc, "Observer_Type", "TEXT", field_length=30)
    return output_fc


def _delete_site_observers(observers_fc: str, site_id: str) -> None:
    if not arcpy.Exists(observers_fc):
        return
    with arcpy.da.UpdateCursor(observers_fc, ["Site_ID"]) as cursor:
        for (value,) in cursor:
            if str(value) == str(site_id):
                cursor.deleteRow()


def run_batch(
    point_sites: str | None,
    line_sites: str | None,
    polygon_sites: str | None,
    site_id_field: str,
    towers: str,
    tower_id_field: str,
    tower_height_field: str,
    tower_height_units: str,
    dem: str,
    output_folder: str,
    dem_vertical_units: str = "Meters",
    observer_height: str = "6 Feet",
    observer_spacing_m: float = 500.0,
    search_distance: str = "5 Miles",
    save_viewshed_rasters: bool = False,
    resume_previous_run: bool = True,
) -> dict:
    """Execute the production batch workflow and return output paths."""
    output_folder = str(Path(output_folder))
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    output_gdb = os.path.join(output_folder, "Visibility_Results.gdb")
    if not arcpy.Exists(output_gdb):
        arcpy.management.CreateFileGDB(output_folder, "Visibility_Results.gdb")

    report_path = os.path.join(output_folder, "Visibility_Analysis_Report.xlsx")
    status_path = os.path.join(output_folder, "run_status.json")
    log_path = os.path.join(output_folder, "run_log.txt")
    viewshed_folder = os.path.join(output_folder, "viewsheds")

    site_layers = [
        (point_sites, "Point"),
        (line_sites, "Line"),
        (polygon_sites, "Polygon"),
    ]
    site_layers = [(dataset, label) for dataset, label in site_layers if dataset]
    if not site_layers:
        raise ValueError("At least one point, line, or polygon site layer is required.")

    valid, qa_rows = run_preflight(
        site_layers,
        site_id_field,
        towers,
        tower_id_field,
        tower_height_field,
        dem,
    )
    if not valid:
        try:
            write_report(report_path, [], [], qa_rows, {"preflight": "FAILED"})
        finally:
            raise RuntimeError("Preflight QA/QC failed. Review the QA Report sheet.")

    extension_name, extension_checked_out_here = _checkout_visibility_extension()
    status = RunStatus(status_path)
    if not resume_previous_run and Path(status_path).exists():
        Path(status_path).unlink()
        status = RunStatus(status_path)

    summary_table = _create_table(output_gdb, "SiteSummary", SUMMARY_FIELDS)
    detail_table = _create_table(output_gdb, "VisibilityDetail", DETAIL_FIELDS)

    if not resume_previous_run:
        arcpy.management.DeleteRows(summary_table)
        arcpy.management.DeleteRows(detail_table)
        existing_observers = os.path.join(output_gdb, "Observers_All")
        if arcpy.Exists(existing_observers):
            arcpy.management.Delete(existing_observers)

    first_sr = arcpy.Describe(site_layers[0][0]).spatialReference
    observers_all = _ensure_observer_output(output_gdb, first_sr)
    scratch_gdb = arcpy.env.scratchGDB
    observer_temp = os.path.join(scratch_gdb, "vva_site_observers")

    config = {
        "observer_height": observer_height,
        "observer_spacing_m": observer_spacing_m,
        "search_distance": search_distance,
        "tower_height_units": tower_height_units,
        "dem_vertical_units": dem_vertical_units,
        "save_viewshed_rasters": save_viewshed_rasters,
        "resume_previous_run": resume_previous_run,
        "dem": dem,
        "viewshed_extension": extension_name,
    }

    log = []
    try:
        for dataset, geometry_label in site_layers:
            shape_type = arcpy.Describe(dataset).shapeType
            with arcpy.da.SearchCursor(dataset, [site_id_field, "SHAPE@"]) as cursor:
                for site_id, geometry in cursor:
                    site_id = str(site_id)
                    if resume_previous_run and status.is_complete(site_id):
                        _message(f"Skipping completed site: {site_id}")
                        continue

                    started = time.perf_counter()
                    _message(f"Processing {geometry_label} site {site_id}...")
                    _delete_site_rows(summary_table, site_id)
                    _delete_site_rows(detail_table, site_id)
                    _delete_site_observers(observers_all, site_id)
                    status.set(site_id, "Running", geometry_type=geometry_label)

                    try:
                        _, observer_count = create_observer_feature_class(
                            geometry,
                            shape_type,
                            site_id,
                            observer_temp,
                            observer_spacing_m,
                        )
                        arcpy.management.Append(observer_temp, observers_all, "NO_TEST")

                        detail_rows, candidate_count = run_site_visibility(
                            site_id=site_id,
                            site_geometry=geometry,
                            observer_fc=observer_temp,
                            towers=towers,
                            tower_id_field=tower_id_field,
                            tower_height_field=tower_height_field,
                            tower_height_units=tower_height_units,
                            dem_vertical_units=dem_vertical_units,
                            dem=dem,
                            observer_height=observer_height,
                            search_distance=search_distance,
                            scratch_gdb=scratch_gdb,
                            save_viewshed=save_viewshed_rasters,
                            viewshed_folder=viewshed_folder,
                        )

                        for detail in detail_rows:
                            _insert_dict(
                                detail_table,
                                detail,
                                [name for name, _, _ in DETAIL_FIELDS],
                            )

                        visible = sum(row["Visibility"] == "Visible" for row in detail_rows)
                        obscured = sum(row["Visibility"] == "Obscured" for row in detail_rows)
                        nodata = sum(row["Visibility"] == "NoData" for row in detail_rows)
                        elapsed = (time.perf_counter() - started) / 60.0
                        summary = {
                            "Site_ID": site_id,
                            "Geometry_Type": geometry_label,
                            "Observer_Count": observer_count,
                            "Candidate_Towers": candidate_count,
                            "Visible_Towers": visible,
                            "Obscured_Towers": obscured,
                            "NoData_Towers": nodata,
                            "Status": "Complete",
                            "Elapsed_Minutes": round(elapsed, 3),
                            "Message": "",
                        }
                        _insert_dict(
                            summary_table,
                            summary,
                            [name for name, _, _ in SUMMARY_FIELDS],
                        )
                        status.set(
                            site_id,
                            "Complete",
                            observer_count=observer_count,
                            candidate_towers=candidate_count,
                            visible_towers=visible,
                            elapsed_minutes=round(elapsed, 3),
                        )
                        log.append(f"COMPLETE | {site_id} | {elapsed:.2f} min")

                    except Exception as exc:
                        elapsed = (time.perf_counter() - started) / 60.0
                        message = str(exc)
                        summary = {
                            "Site_ID": site_id,
                            "Geometry_Type": geometry_label,
                            "Observer_Count": 0,
                            "Candidate_Towers": 0,
                            "Visible_Towers": 0,
                            "Obscured_Towers": 0,
                            "NoData_Towers": 0,
                            "Status": "Failed",
                            "Elapsed_Minutes": round(elapsed, 3),
                            "Message": message[:1000],
                        }
                        _insert_dict(
                            summary_table,
                            summary,
                            [name for name, _, _ in SUMMARY_FIELDS],
                        )
                        status.set(
                            site_id,
                            "Failed",
                            message=message,
                            elapsed_minutes=round(elapsed, 3),
                        )
                        log.append(f"FAILED | {site_id} | {message}")
                        _warning(f"Site {site_id} failed: {message}")

        summary_columns = [name for name, _, _ in SUMMARY_FIELDS]
        detail_columns = [name for name, _, _ in DETAIL_FIELDS]
        summary_rows = _read_table(summary_table, summary_columns)
        detail_rows = _read_table(detail_table, detail_columns)
        write_report(report_path, summary_rows, detail_rows, qa_rows, config)
        Path(log_path).write_text("\n".join(log) + ("\n" if log else ""), encoding="utf-8")
    finally:
        if extension_checked_out_here:
            arcpy.CheckInExtension(extension_name)

    return {
        "output_gdb": output_gdb,
        "excel_report": report_path,
        "status_json": status_path,
        "run_log": log_path,
        "viewshed_folder": viewshed_folder if save_viewshed_rasters else None,
    }
