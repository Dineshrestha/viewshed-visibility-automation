"""Generate deterministic synthetic demo data for the public portfolio project.

Run with the ArcGIS Pro Python environment. The geometry is synthetic; the
location is chosen only so the demo can use real public USGS terrain.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import arcpy


SEED = 42
WKID = 26913  # NAD83 / UTM zone 13N
CENTER_X = 500_000.0
CENTER_Y = 4_390_000.0
HALF_SIZE = 30_000.0


def _create_fc(gdb: str, name: str, geometry_type: str, sr) -> str:
    fc = str(Path(gdb) / name)
    if arcpy.Exists(fc):
        arcpy.management.Delete(fc)
    arcpy.management.CreateFeatureclass(gdb, name, geometry_type, spatial_reference=sr)
    return fc


def _add_site_fields(fc: str) -> None:
    arcpy.management.AddField(fc, "Site_ID", "TEXT", field_length=30)
    arcpy.management.AddField(fc, "Site_Name", "TEXT", field_length=80)


def generate(output_folder: str | None = None) -> dict:
    random.seed(SEED)
    root = Path(output_folder) if output_folder else Path(__file__).resolve().parent / "demo_data"
    root.mkdir(parents=True, exist_ok=True)
    gdb = root / "DemoData.gdb"
    if arcpy.Exists(str(gdb)):
        arcpy.management.Delete(str(gdb))
    arcpy.management.CreateFileGDB(str(root), gdb.name)

    sr = arcpy.SpatialReference(WKID)
    study_area = _create_fc(str(gdb), "Study_Area", "POLYGON", sr)
    point_sites = _create_fc(str(gdb), "Observation_Sites_Point", "POINT", sr)
    line_sites = _create_fc(str(gdb), "Observation_Sites_Line", "POLYLINE", sr)
    polygon_sites = _create_fc(str(gdb), "Observation_Sites_Polygon", "POLYGON", sr)
    towers = _create_fc(str(gdb), "Towers", "POINT", sr)

    for fc in (point_sites, line_sites, polygon_sites):
        _add_site_fields(fc)
    arcpy.management.AddField(towers, "Tower_ID", "TEXT", field_length=30)
    arcpy.management.AddField(towers, "Height_ft", "DOUBLE")
    arcpy.management.AddField(towers, "Tower_Type", "TEXT", field_length=30)

    xmin = CENTER_X - HALF_SIZE
    xmax = CENTER_X + HALF_SIZE
    ymin = CENTER_Y - HALF_SIZE
    ymax = CENTER_Y + HALF_SIZE
    ring = arcpy.Array(
        [
            arcpy.Point(xmin, ymin),
            arcpy.Point(xmax, ymin),
            arcpy.Point(xmax, ymax),
            arcpy.Point(xmin, ymax),
            arcpy.Point(xmin, ymin),
        ]
    )
    with arcpy.da.InsertCursor(study_area, ["SHAPE@"]) as cursor:
        cursor.insertRow([arcpy.Polygon(ring, sr)])

    margin = 4_000.0

    with arcpy.da.InsertCursor(point_sites, ["SHAPE@", "Site_ID", "Site_Name"]) as cursor:
        for i in range(1, 36):
            x = random.uniform(xmin + margin, xmax - margin)
            y = random.uniform(ymin + margin, ymax - margin)
            cursor.insertRow(
                [arcpy.PointGeometry(arcpy.Point(x, y), sr), f"P{i:03d}", f"Point Site {i:03d}"]
            )

    with arcpy.da.InsertCursor(line_sites, ["SHAPE@", "Site_ID", "Site_Name"]) as cursor:
        for i in range(1, 31):
            cx = random.uniform(xmin + 7_000, xmax - 7_000)
            cy = random.uniform(ymin + 7_000, ymax - 7_000)
            angle = random.uniform(0, math.tau)
            length = random.uniform(1_200, 5_000)
            bend = random.uniform(-700, 700)
            dx = math.cos(angle) * length / 2
            dy = math.sin(angle) * length / 2
            perp_x = -math.sin(angle) * bend
            perp_y = math.cos(angle) * bend
            points = arcpy.Array(
                [
                    arcpy.Point(cx - dx, cy - dy),
                    arcpy.Point(cx + perp_x, cy + perp_y),
                    arcpy.Point(cx + dx, cy + dy),
                ]
            )
            cursor.insertRow([arcpy.Polyline(points, sr), f"L{i:03d}", f"Line Site {i:03d}"])

    with arcpy.da.InsertCursor(polygon_sites, ["SHAPE@", "Site_ID", "Site_Name"]) as cursor:
        for i in range(1, 26):
            cx = random.uniform(xmin + 6_000, xmax - 6_000)
            cy = random.uniform(ymin + 6_000, ymax - 6_000)
            width = random.uniform(700, 3_000)
            height = random.uniform(700, 3_000)
            ring = arcpy.Array(
                [
                    arcpy.Point(cx - width / 2, cy - height / 2),
                    arcpy.Point(cx + width / 2, cy - height / 2),
                    arcpy.Point(cx + width / 2, cy + height / 2),
                    arcpy.Point(cx - width / 2, cy + height / 2),
                    arcpy.Point(cx - width / 2, cy - height / 2),
                ]
            )
            cursor.insertRow([arcpy.Polygon(ring, sr), f"A{i:03d}", f"Area Site {i:03d}"])

    tower_types = ["Transmission", "Communications", "Monitoring"]
    with arcpy.da.InsertCursor(
        towers,
        ["SHAPE@", "Tower_ID", "Height_ft", "Tower_Type"],
    ) as cursor:
        for i in range(1, 66):
            x = random.uniform(xmin + 1_000, xmax - 1_000)
            y = random.uniform(ymin + 1_000, ymax - 1_000)
            height_ft = round(random.uniform(80, 320), 1)
            cursor.insertRow(
                [
                    arcpy.PointGeometry(arcpy.Point(x, y), sr),
                    f"TWR-{i:03d}",
                    height_ft,
                    random.choice(tower_types),
                ]
            )

    print(f"Synthetic demo geodatabase created: {gdb}")
    print("Sites: 35 point + 30 line + 25 polygon = 90")
    print("Towers: 65")
    return {
        "gdb": str(gdb),
        "study_area": study_area,
        "point_sites": point_sites,
        "line_sites": line_sites,
        "polygon_sites": polygon_sites,
        "towers": towers,
    }


if __name__ == "__main__":
    generate()
