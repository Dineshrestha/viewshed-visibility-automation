# Methodology

## Decision question

For each observation site, which candidate towers are potentially visible through terrain when both observer height and target tower height are considered?

## Any Location representation

A point site has one observer. A line is sampled at a configurable interval. A polygon receives interior-grid, boundary, and interior label-point observers. The purpose is to approximate visibility from the full geometry rather than assume that one midpoint or centroid adequately represents the site.

A tower is potentially visible from a site if at least one generated observer can see enough above-ground height at the tower location for the tower to intersect the line of sight.

## AGL classification

ArcGIS Geodesic Viewshed can create an Above Ground Level (AGL) raster. The AGL cell value is the minimum additional height required at a nonvisible cell for it to become visible from at least one observer; already visible cells receive 0.

For each candidate tower:

```text
TowerHeight_m >= RequiredAGL_m  -> Visible
TowerHeight_m <  RequiredAGL_m  -> Obscured
NoData at target                -> NoData / review
```

This is more informative than sampling only the binary ground-level viewshed because the target's actual height participates in the classification.

## Distance rule

Candidate towers are selected within the configured search distance of the original site geometry. The same distance is supplied as the ground-distance outer radius to Geodesic Viewshed.

## Elevation strategy

The public implementation uses the USGS 3DEP Bare Earth DEM dynamic ImageServer:

https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer

The default output cell size is 30 m. Large bounding extents are divided into image-service tiles, mosaicked, projected into the study-area coordinate system, and clipped to the buffered AOI.

## Why 30 m by default

The original engineering process tested higher-resolution elevation, including 10 m. Higher resolution can improve terrain representation, but it also increases cell count, storage, transfer, and viewshed processing cost. For a large batch, 30 m was selected as a practical production tradeoff. This is a configurable decision, not a universal rule.

## Caveats

This is terrain visibility. Buildings, vegetation, haze, local screening, and transient obstructions are not modeled unless represented in the input surface. Results should therefore be described as *potential visibility* and verified appropriately for the decision context.
