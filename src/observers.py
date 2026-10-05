"""Generate representative observer points for mixed geometry sites."""

from __future__ import annotations

import os

import arcpy


def _xy_key(point_geometry, precision: int = 3):
    p = point_geometry.firstPoint
    return round(p.X, precision), round(p.Y, precision)


def _dedupe(points):
    seen = set()
    output = []
    for point in points:
        key = _xy_key(point)
        if key not in seen:
            seen.add(key)
            output.append(point)
    return output


def _points_along_polyline(polyline, spacing_units: float):
    points = []
    length = polyline.length
    if length <= 0:
        return points
    distance = 0.0
    while distance < length:
        points.append(polyline.positionAlongLine(distance, False))
        distance += spacing_units
    points.append(polyline.positionAlongLine(length, False))
    return points


def _polygon_boundary_polylines(polygon, spatial_reference):
    """Convert polygon rings to temporary Polyline geometry objects."""
    lines = []
    for part in polygon:
        current = arcpy.Array()
        for point in part:
            if point is None:
                if current.count >= 2:
                    lines.append(arcpy.Polyline(current, spatial_reference))
                current = arcpy.Array()
            else:
                current.add(point)
        if current.count >= 2:
            lines.append(arcpy.Polyline(current, spatial_reference))
    return lines


def observer_points_for_geometry(geometry, geometry_type: str, spacing_m: float):
    """Return PointGeometry observers representing one site geometry."""
    sr = geometry.spatialReference
    meters_per_unit = getattr(sr, "metersPerUnit", None) or 1.0
    spacing_units = float(spacing_m) / float(meters_per_unit)
    geometry_type = geometry_type.lower()

    if geometry_type == "point":
        return [geometry]

    if geometry_type == "polyline":
        return _dedupe(_points_along_polyline(geometry, spacing_units))

    if geometry_type != "polygon":
        raise ValueError(f"Unsupported site geometry type: {geometry_type}")

    points = []
    label_point = arcpy.PointGeometry(geometry.labelPoint, sr)
    points.append(label_point)

    # Interior grid. Offset from the bounding-box edge by half a spacing.
    extent = geometry.extent
    start_x = extent.XMin + spacing_units / 2.0
    start_y = extent.YMin + spacing_units / 2.0
    x = start_x
    while x <= extent.XMax:
        y = start_y
        while y <= extent.YMax:
            candidate = arcpy.PointGeometry(arcpy.Point(x, y), sr)
            if candidate.within(geometry):
                points.append(candidate)
            y += spacing_units
        x += spacing_units

    # Boundary coverage matters because an interior centroid/grid alone can miss
    # a visible edge location under the Any Location decision rule.
    for boundary_line in _polygon_boundary_polylines(geometry, sr):
        points.extend(_points_along_polyline(boundary_line, spacing_units))

    return _dedupe(points)


def create_observer_feature_class(
    geometry,
    geometry_type: str,
    site_id: str,
    output_fc: str,
    spacing_m: float = 500.0,
) -> tuple[str, int]:
    """Write representative observer points for one site."""
    if arcpy.Exists(output_fc):
        arcpy.management.Delete(output_fc)

    workspace, name = os.path.split(output_fc)
    arcpy.management.CreateFeatureclass(
        workspace,
        name,
        "POINT",
        spatial_reference=geometry.spatialReference,
    )
    arcpy.management.AddField(output_fc, "Site_ID", "TEXT", field_length=100)
    arcpy.management.AddField(output_fc, "Observer_ID", "TEXT", field_length=120)
    arcpy.management.AddField(output_fc, "Observer_Type", "TEXT", field_length=30)

    observers = observer_points_for_geometry(geometry, geometry_type, spacing_m)
    with arcpy.da.InsertCursor(
        output_fc,
        ["SHAPE@", "Site_ID", "Observer_ID", "Observer_Type"],
    ) as cursor:
        for index, point in enumerate(observers, start=1):
            cursor.insertRow(
                [
                    point,
                    str(site_id),
                    f"{site_id}_OBS_{index:04d}",
                    geometry_type,
                ]
            )
    return output_fc, len(observers)
