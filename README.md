# Viewshed & Visibility Automation

**270+ manual hours → ~16 hours for the first implementation → ~4 labor-hours for comparable repeat runs**

A reusable ArcGIS Pro / ArcPy workflow for batch terrain visibility analysis from mixed **point, line, and polygon observation sites** to **tower/structure targets**. The project automates DEM preparation, observer generation, geodesic viewshed processing, target-height visibility classification, QA/QC, resumable batch execution, and Excel reporting.

> Portfolio note: this repository uses a new synthetic scenario and public elevation data. It contains no employer, client, project, cultural-resource, proprietary, or restricted data.

## Why this project exists

A validated one-site workflow required roughly three labor-hours when performed manually. Scaling that approach to about 90 mixed-geometry sites implied at least **270 labor-hours**, with line and polygon sites requiring additional work because a midpoint or centroid alone does not represent visibility from the full site geometry.

The first automated implementation required about **16 total labor-hours**:

| Effort | Approx. labor | What it included |
|---|---:|---|
| One-time engineering | ~12 hrs | methodology design, scripting, Python Toolbox design, DEM acquisition, 10 m vs 30 m evaluation, observer strategy, troubleshooting, test runs, QA/QC |
| Production execution / validation | ~4 hrs | selected-site runs, iterative checks, final batch execution, result review |
| **First delivery** | **~16 hrs** | engineering + production |
| **Comparable repeat run** | **~4 hrs** | reuse the existing system; execute and validate |

Against the conservative 270-hour manual baseline, that is roughly **94% less labor on the first implementation** and **98.5% less recurring labor on comparable repeat runs**. These figures describe labor effort, not machine runtime; runtime varies by study-area size, site count, observer spacing, DEM extent, hardware, and ArcGIS configuration.

## What the system does

```text
Observation Sites (point / line / polygon)
                 │
                 ▼
          Preflight QA/QC
                 │
                 ▼
     Generate Site Observers
 point = 1 | line = spaced | polygon = grid + boundary
                 │
                 ▼
   Prepare / Validate 30 m DEM
        USGS 3DEP ImageServer
                 │
                 ▼
      Geodesic Viewshed + AGL
                 │
                 ▼
  Sample AGL at candidate towers
                 │
                 ▼
Tower height >= required AGL ?
          │               │
        YES              NO
          │               │
      Visible         Obscured
                 │
                 ▼
 Excel Report + GIS Outputs + Run Log
```

The key visibility rule uses the **Above Ground Level (AGL)** raster produced by ArcGIS Geodesic Viewshed. At each target tower, the workflow compares the tower height with the minimum above-ground height required for that location to become visible from at least one observer. This lets the target's physical height participate in the visibility decision rather than treating every tower as a ground-level point.

## Final product

The end-user product is an ArcGIS Pro Python Toolbox:

```text
ViewshedVisibilityAutomation.pyt
├── Prepare 30 m DEM
└── Batch Viewshed & Visibility
```

The toolbox is intentionally a thin UI layer. Core processing logic lives in importable modules under `src/` so it can also be scripted, tested, and extended.

### Tool 1 — Prepare 30 m DEM

Accepts a study area, buffers it, retrieves public USGS 3DEP elevation through the 3DEP ImageServer, tiles requests when necessary, mosaics the tiles, projects the DEM to the study area's projected coordinate system, and clips it to the buffered analysis extent.

### Tool 2 — Batch Viewshed & Visibility

Accepts point, line, and/or polygon observation sites plus a tower/structure layer and prepared DEM. It generates observers, performs site-by-site geodesic viewshed analysis, classifies target visibility, continues past individual site failures, supports resume/restart, optionally preserves per-site viewshed rasters, and writes a structured Excel report.

## Default analysis settings

| Setting | Default |
|---|---:|
| Observer height | 6 ft |
| Line/polygon observer spacing | 500 m |
| Target search / viewshed distance | 5 miles |
| DEM output resolution | 30 m |
| DEM vertical units | meters |
| Save per-site viewshed rasters | No |
| Resume completed sites | Yes |

## Mixed-geometry methodology

A single centroid or midpoint can miss visibility that exists elsewhere on a site. The workflow therefore represents geometry differently:

- **Point:** the feature itself becomes one observer.
- **Line:** observers are distributed along the line at the configured spacing, with endpoints retained.
- **Polygon:** observers are distributed through the polygon interior and along its boundary, with an interior label point retained.

The production decision rule is **Any Location**: a target is potentially visible when it is visible from at least one observer representing that site.

## DEM strategy

The default public elevation source is the USGS **3D Elevation Program (3DEP) Bare Earth DEM dynamic ImageServer**. The public portfolio implementation requests a 30 m analysis raster for scalable batch processing and tiles large image-service requests before mosaicking, projecting, and clipping them.

The original engineering exercise also evaluated 10 m elevation. Higher resolution improved terrain detail but increased storage and processing cost at batch scale, so 30 m became the practical production default. Resolution remains configurable.

## Repository structure

```text
viewshed-visibility-automation/
├── README.md
├── LICENSE
├── requirements.txt
├── config/defaults.json
├── data/
│   ├── README.md
│   └── generate_demo_data.py
├── docs/
│   ├── architecture.md
│   ├── benchmark.md
│   └── methodology.md
├── src/
│   ├── analysis.py
│   ├── dem.py
│   ├── observers.py
│   ├── reporting.py
│   ├── runner.py
│   ├── status.py
│   ├── utils.py
│   └── validation.py
├── tests/
└── toolbox/ViewshedVisibilityAutomation.pyt
```

## Quick start

1. Use **ArcGIS Pro 3.x** with the **Spatial Analyst** extension and `openpyxl` available in the ArcGIS Python environment. `arcpy` is provided by ArcGIS Pro and should not be installed from PyPI.
2. Run `data/generate_demo_data.py` to create a deterministic synthetic geodatabase containing 90 mixed-geometry sites and 65 towers.
3. Add `toolbox/ViewshedVisibilityAutomation.pyt` to ArcGIS Pro and run **Prepare 30 m DEM** using the generated study area.
4. Run **Batch Viewshed & Visibility** using the synthetic site layers, tower layer, and prepared DEM.
5. Review `Visibility_Results.gdb`, `Visibility_Analysis_Report.xlsx`, `run_status.json`, `run_log.txt`, and optional per-site viewshed rasters.

## QA/QC and resume behavior

The workflow fails early for structural problems and fails locally for site-specific problems. Preflight checks cover projected coordinate systems, unique/non-null IDs, positive tower heights, DEM properties, and Spatial Analyst availability. During a batch, one bad site is logged and marked failed without discarding successful sites.

`run_status.json` checkpoints every site. With resume enabled, completed sites are skipped on the next execution so a crash or isolated failure does not force a full restart.

## Important limitations

- USGS 3DEP coverage and source resolution vary by location; the DEM-preparation tool is primarily for U.S. study areas covered by 3DEP.
- A 30 m DEM is a production tradeoff, not a universal accuracy standard.
- Visibility is terrain-based and does not model buildings, vegetation, atmospheric effects, or other non-DEM obstructions unless they are represented in the surface.
- “Potentially visible” is a GIS screening result, not a substitute for field verification.
- The ~4-hour repeat-run figure is a labor-effort benchmark from the originating engineering workflow, not a guaranteed runtime or SLA.

## Engineering principles demonstrated

ArcPy geoprocessing, raster/vector integration, mixed-geometry handling, spatial methodology design, public-data acquisition, batch processing, fault isolation, checkpoint/resume design, QA/QC, reproducibility, configurable business rules, Excel automation, testing, and Python Toolbox productization.

## License

MIT License. See `LICENSE`.
