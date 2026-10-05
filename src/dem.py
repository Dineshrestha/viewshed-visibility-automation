"""USGS 3DEP DEM acquisition and preparation."""

from __future__ import annotations

import os
from pathlib import Path

import arcpy

from .utils import tile_ranges


DEFAULT_3DEP_SERVICE = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/"
    "3DEPElevation/ImageServer"
)
WEB_MERCATOR_WKID = 3857


def _log(message: str) -> None:
    try:
        arcpy.AddMessage(message)
    except Exception:
        print(message)


def prepare_dem(
    study_area: str,
    output_dem: str,
    buffer_distance: str = "5 Miles",
    cell_size_m: float = 30.0,
    service_url: str = DEFAULT_3DEP_SERVICE,
    tile_pixels: int = 7000,
) -> str:
    """Download, mosaic, project and clip a 3DEP DEM for a study area.

    Large service requests are divided into Web Mercator tiles so the workflow
    does not depend on a single image export exceeding server image dimensions.
    The final DEM is projected to the study area's projected coordinate system.

    DEM preparation intentionally uses Data Management tools only for the final
    raster clip, so a Spatial Analyst extension is not required for this step.
    """
    if float(cell_size_m) <= 0:
        raise ValueError("cell_size_m must be positive")
    if int(tile_pixels) <= 0:
        raise ValueError("tile_pixels must be positive")

    desc = arcpy.Describe(study_area)
    sr = desc.spatialReference
    if not sr or sr.type != "Projected":
        raise ValueError("Study area must use a projected coordinate system.")

    output_dem = str(output_dem)
    scratch_gdb = arcpy.env.scratchGDB
    if not scratch_gdb:
        raise RuntimeError("ArcPy scratchGDB is unavailable.")

    buffer_fc = os.path.join(scratch_gdb, "vva_dem_buffer")
    buffer_3857 = os.path.join(scratch_gdb, "vva_dem_buffer_3857")
    for item in (buffer_fc, buffer_3857):
        if arcpy.Exists(item):
            arcpy.management.Delete(item)

    _log(f"Buffering study area by {buffer_distance}...")
    arcpy.analysis.Buffer(study_area, buffer_fc, buffer_distance, dissolve_option="ALL")
    arcpy.management.Project(buffer_fc, buffer_3857, arcpy.SpatialReference(WEB_MERCATOR_WKID))

    extent = arcpy.Describe(buffer_3857).extent
    tile_span = float(cell_size_m) * int(tile_pixels)
    x_ranges = list(tile_ranges(extent.XMin, extent.XMax, tile_span))
    y_ranges = list(tile_ranges(extent.YMin, extent.YMax, tile_span))
    tile_count = len(x_ranges) * len(y_ranges)
    _log(f"3DEP request will use {tile_count} tile(s) at {cell_size_m:g} m.")

    tile_folder = Path(arcpy.env.scratchFolder) / "vva_dem_tiles"
    tile_folder.mkdir(parents=True, exist_ok=True)
    tile_paths: list[str] = []

    idx = 0
    for x0, x1 in x_ranges:
        for y0, y1 in y_ranges:
            idx += 1
            layer_name = f"vva_3dep_{idx}"
            tile_path = str(tile_folder / f"tile_{idx:03d}.tif")
            if arcpy.Exists(tile_path):
                arcpy.management.Delete(tile_path)

            template = f"{x0} {y0} {x1} {y1}"
            _log(f"Downloading DEM tile {idx}/{tile_count}...")
            arcpy.management.MakeImageServerLayer(
                service_url,
                layer_name,
                template,
                cell_size=float(cell_size_m),
            )
            arcpy.management.CopyRaster(
                layer_name,
                tile_path,
                pixel_type="32_BIT_FLOAT",
                format="TIFF",
            )
            tile_paths.append(tile_path)
            arcpy.management.Delete(layer_name)

    raw_3857 = str(tile_folder / "dem_mosaic_3857.tif")
    if arcpy.Exists(raw_3857):
        arcpy.management.Delete(raw_3857)

    if len(tile_paths) == 1:
        arcpy.management.CopyRaster(tile_paths[0], raw_3857, pixel_type="32_BIT_FLOAT")
    else:
        arcpy.management.MosaicToNewRaster(
            tile_paths,
            str(tile_folder),
            Path(raw_3857).name,
            arcpy.SpatialReference(WEB_MERCATOR_WKID),
            "32_BIT_FLOAT",
            float(cell_size_m),
            1,
            "MEAN",
            "FIRST",
        )

    projected = str(tile_folder / "dem_projected.tif")
    if arcpy.Exists(projected):
        arcpy.management.Delete(projected)

    _log("Projecting DEM to study-area coordinate system...")
    meters_per_unit = getattr(sr, "metersPerUnit", None) or 1.0
    target_cell_size = float(cell_size_m) / float(meters_per_unit)
    arcpy.management.ProjectRaster(
        raw_3857,
        projected,
        sr,
        "BILINEAR",
        target_cell_size,
    )

    if arcpy.Exists(output_dem):
        arcpy.management.Delete(output_dem)

    _log("Clipping DEM to buffered study area...")
    arcpy.management.Clip(
        projected,
        "#",
        output_dem,
        buffer_fc,
        "#",
        "ClippingGeometry",
        "NO_MAINTAIN_EXTENT",
    )
    _log(f"DEM ready: {output_dem}")
    return output_dem
