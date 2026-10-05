# -*- coding: utf-8 -*-
"""ArcGIS Pro Python Toolbox for Viewshed & Visibility Automation."""

from __future__ import annotations

import sys
from pathlib import Path

import arcpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.dem import DEFAULT_3DEP_SERVICE, prepare_dem
from src.runner import run_batch


class Toolbox:
    def __init__(self):
        self.label = "Viewshed & Visibility Automation"
        self.alias = "viewshed_visibility_automation"
        self.tools = [PrepareDEM, BatchViewshedVisibility]


class PrepareDEM:
    def __init__(self):
        self.label = "Prepare 30 m DEM"
        self.description = (
            "Download and prepare a USGS 3DEP DEM for a projected study area. "
            "Large requests are tiled automatically."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        study_area = arcpy.Parameter(
            displayName="Study Area",
            name="study_area",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        study_area.filter.list = ["Polygon"]

        buffer_distance = arcpy.Parameter(
            displayName="DEM Buffer Distance",
            name="buffer_distance",
            datatype="GPLinearUnit",
            parameterType="Required",
            direction="Input",
        )
        buffer_distance.value = "5 Miles"

        cell_size = arcpy.Parameter(
            displayName="Output Cell Size (meters)",
            name="cell_size_m",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
        )
        cell_size.value = 30

        service_url = arcpy.Parameter(
            displayName="USGS 3DEP ImageServer URL",
            name="service_url",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        service_url.value = DEFAULT_3DEP_SERVICE

        output_dem = arcpy.Parameter(
            displayName="Output DEM",
            name="output_dem",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Output",
        )

        return [study_area, buffer_distance, cell_size, service_url, output_dem]

    def execute(self, parameters, messages):
        prepare_dem(
            study_area=parameters[0].valueAsText,
            buffer_distance=parameters[1].valueAsText,
            cell_size_m=float(parameters[2].value),
            service_url=parameters[3].valueAsText or DEFAULT_3DEP_SERVICE,
            output_dem=parameters[4].valueAsText,
        )
        return


class BatchViewshedVisibility:
    def __init__(self):
        self.label = "Batch Viewshed & Visibility"
        self.description = (
            "Generate mixed-geometry observers and classify structure visibility. "
            "Auto uses ArcGIS Geodesic Viewshed when licensed and otherwise falls "
            "back to extension-free NumPy direct line-of-sight analysis."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        point_sites = arcpy.Parameter(
            displayName="Point Observation Sites",
            name="point_sites",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
        )
        point_sites.filter.list = ["Point"]

        line_sites = arcpy.Parameter(
            displayName="Line Observation Sites",
            name="line_sites",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
        )
        line_sites.filter.list = ["Polyline"]

        polygon_sites = arcpy.Parameter(
            displayName="Polygon Observation Sites",
            name="polygon_sites",
            datatype="GPFeatureLayer",
            parameterType="Optional",
            direction="Input",
        )
        polygon_sites.filter.list = ["Polygon"]

        site_id = arcpy.Parameter(
            displayName="Site ID Field (same field name in supplied site layers)",
            name="site_id_field",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        site_id.value = "Site_ID"

        towers = arcpy.Parameter(
            displayName="Tower / Structure Points",
            name="towers",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        towers.filter.list = ["Point"]

        tower_id = arcpy.Parameter(
            displayName="Tower ID Field",
            name="tower_id_field",
            datatype="Field",
            parameterType="Required",
            direction="Input",
        )
        tower_id.parameterDependencies = [towers.name]

        tower_height = arcpy.Parameter(
            displayName="Tower Height Field",
            name="tower_height_field",
            datatype="Field",
            parameterType="Required",
            direction="Input",
        )
        tower_height.parameterDependencies = [towers.name]

        height_units = arcpy.Parameter(
            displayName="Tower Height Units",
            name="tower_height_units",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        height_units.filter.type = "ValueList"
        height_units.filter.list = ["Feet", "Meters"]
        height_units.value = "Feet"

        dem = arcpy.Parameter(
            displayName="Elevation DEM",
            name="dem",
            datatype="GPRasterLayer",
            parameterType="Required",
            direction="Input",
        )

        dem_vertical_units = arcpy.Parameter(
            displayName="DEM Elevation Units",
            name="dem_vertical_units",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        dem_vertical_units.filter.type = "ValueList"
        dem_vertical_units.filter.list = ["Meters", "Feet"]
        dem_vertical_units.value = "Meters"

        observer_height = arcpy.Parameter(
            displayName="Observer Height",
            name="observer_height",
            datatype="GPLinearUnit",
            parameterType="Required",
            direction="Input",
        )
        observer_height.value = "6 Feet"

        observer_spacing = arcpy.Parameter(
            displayName="Line / Polygon Observer Spacing (meters)",
            name="observer_spacing_m",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
        )
        observer_spacing.value = 500

        search_distance = arcpy.Parameter(
            displayName="Target Search / Visibility Distance",
            name="search_distance",
            datatype="GPLinearUnit",
            parameterType="Required",
            direction="Input",
        )
        search_distance.value = "5 Miles"

        visibility_engine = arcpy.Parameter(
            displayName="Visibility Engine",
            name="visibility_engine",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        visibility_engine.filter.type = "ValueList"
        visibility_engine.filter.list = [
            "Auto",
            "ArcGIS Geodesic Viewshed",
            "NumPy Direct LOS",
        ]
        visibility_engine.value = "Auto"

        save_viewsheds = arcpy.Parameter(
            displayName="Save Per-Site Viewshed Rasters",
            name="save_viewshed_rasters",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input",
        )
        save_viewsheds.value = False

        resume = arcpy.Parameter(
            displayName="Resume Previous Run / Skip Completed Sites",
            name="resume_previous_run",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input",
        )
        resume.value = True

        output_folder = arcpy.Parameter(
            displayName="Output Folder",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input",
        )

        return [
            point_sites,
            line_sites,
            polygon_sites,
            site_id,
            towers,
            tower_id,
            tower_height,
            height_units,
            dem,
            dem_vertical_units,
            observer_height,
            observer_spacing,
            search_distance,
            visibility_engine,
            save_viewsheds,
            resume,
            output_folder,
        ]

    def execute(self, parameters, messages):
        outputs = run_batch(
            point_sites=parameters[0].valueAsText,
            line_sites=parameters[1].valueAsText,
            polygon_sites=parameters[2].valueAsText,
            site_id_field=parameters[3].valueAsText,
            towers=parameters[4].valueAsText,
            tower_id_field=parameters[5].valueAsText,
            tower_height_field=parameters[6].valueAsText,
            tower_height_units=parameters[7].valueAsText,
            dem=parameters[8].valueAsText,
            dem_vertical_units=parameters[9].valueAsText,
            observer_height=parameters[10].valueAsText,
            observer_spacing_m=float(parameters[11].value),
            search_distance=parameters[12].valueAsText,
            visibility_engine=parameters[13].valueAsText,
            save_viewshed_rasters=bool(parameters[14].value),
            resume_previous_run=bool(parameters[15].value),
            output_folder=parameters[16].valueAsText,
        )
        arcpy.AddMessage(f"Results geodatabase: {outputs['output_gdb']}")
        arcpy.AddMessage(f"Excel report: {outputs['excel_report']}")
        return
