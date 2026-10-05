# Demo data

No proprietary source data is stored in this repository.

Run `generate_demo_data.py` with the ArcGIS Pro Python environment to create a deterministic synthetic geodatabase containing:

- 1 study-area polygon
- 35 point observation sites
- 30 line observation sites
- 25 polygon observation sites
- 65 synthetic towers with height attributes

The fixed random seed is `42`. The geometries are synthetic and are placed over public terrain in Colorado so the demo can exercise USGS 3DEP elevation data.

The generated `demo_data/` directory is intentionally ignored by Git.
