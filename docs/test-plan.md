# ArcGIS Pro integration test plan

The pure-Python helpers and checkpoint/reporting components can be tested outside ArcGIS. The geoprocessing engine must be validated inside an ArcGIS Pro Python environment because `arcpy`, Spatial Analyst, Geodesic Viewshed, image services, and file geodatabases are ArcGIS-specific.

## Stage 1 — Generate demo data

Run `data/generate_demo_data.py` with the ArcGIS Pro Python environment.

Expected outputs in `data/demo_data/DemoData.gdb`:

- `Study_Area`: 1 polygon
- `Observation_Sites_Point`: 35 features
- `Observation_Sites_Line`: 30 features
- `Observation_Sites_Polygon`: 25 features
- `Towers`: 65 features

All site layers should contain `Site_ID`; towers should contain `Tower_ID` and `Height_ft`.

## Stage 2 — Load the toolbox

Add `toolbox/ViewshedVisibilityAutomation.pyt` to ArcGIS Pro.

Expected tools:

1. `Prepare 30 m DEM`
2. `Batch Viewshed & Visibility`

## Stage 3 — DEM smoke test

Run **Prepare 30 m DEM** with:

- Study Area: `Study_Area`
- Buffer: `5 Miles`
- Cell Size: `30`
- Service URL: default USGS 3DEP ImageServer
- Output: a local TIFF or file-geodatabase raster

Validate:

- output raster exists
- output CRS matches the projected study-area CRS
- cell size is approximately 30 m
- buffered study area is covered
- raster contains valid elevation values rather than all NoData

## Stage 4 — Small batch smoke test

Before running all 90 sites, select 2–3 point sites in ArcGIS Pro and pass the selected point layer to **Batch Viewshed & Visibility**. Leave line and polygon inputs blank.

Use:

- Site ID: `Site_ID`
- Towers: `Towers`
- Tower ID: `Tower_ID`
- Tower Height: `Height_ft`
- Tower Height Units: `Feet`
- DEM Elevation Units: `Meters`
- Observer Height: `6 Feet`
- Observer Spacing: `500`
- Search Distance: `5 Miles`
- Save Viewshed Rasters: `False`
- Resume Previous Run: `True`

Validate:

- `Visibility_Results.gdb` is created
- `Observers_All` contains one observer per selected point site
- `SiteSummary` contains one record per selected site
- `VisibilityDetail` contains site-to-tower relationships for candidate towers
- `Visibility_Analysis_Report.xlsx` opens successfully
- `run_status.json` marks completed sites as `Complete`
- `run_log.txt` records processing outcomes

## Stage 5 — Mixed-geometry test

Run one selected line and one selected polygon site.

Validate:

- line site produces multiple observers at approximately the configured spacing
- polygon site produces interior and boundary observers
- output summary observer counts are greater than one for sufficiently large geometries
- processing continues if an individual site fails

## Stage 6 — Resume test

Re-run the same output folder with **Resume Previous Run = True**.

Validate that previously completed sites are skipped rather than recomputed.

## Stage 7 — Full synthetic run

Run all 90 synthetic sites. At completion:

- `SiteSummary` should reconcile to 90 sites unless an intentionally logged failure occurred
- every failed site should have an explicit message
- Excel summary/detail counts should reconcile to geodatabase tables
- no site should disappear silently

## Stage 8 — Optional viewshed retention

Run a small subset with **Save Per-Site Viewshed Rasters = True** and confirm that named viewshed TIFFs are retained in the `viewsheds/` folder.

## Acceptance decision

Merge the v1 branch after Stages 1–6 pass. The full 90-site run is the portfolio benchmark/demo validation and can then be captured with screenshots and final timing metrics.
