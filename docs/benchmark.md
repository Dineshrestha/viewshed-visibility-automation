# Labor-efficiency benchmark

The portfolio claim separates one-time engineering from recurring execution.

| Scenario | Labor effort |
|---|---:|
| Manual one-site workflow | ~3 hrs/site |
| 90-site manual equivalent | ~270+ hrs |
| One-time engineering / R&D | ~12 hrs |
| First production execution and validation | ~4 hrs |
| First implementation total | ~16 hrs |
| Comparable repeat production run | ~4 hrs |

## First implementation

Using the conservative 270-hour baseline:

- Labor avoided: about `270 - 16 = 254` hours
- Labor reduction: about `254 / 270 = 94.1%`
- Labor-efficiency factor: about `270 / 16 = 16.9x`

## Comparable repeat run

Once the methodology, code, toolbox, DEM workflow, QA rules, and reporting system already exist:

- Labor avoided: about `270 - 4 = 266` hours
- Labor reduction: about `266 / 270 = 98.5%`
- Labor-efficiency factor: about `270 / 4 = 67.5x`

The repeat-run figure is **labor effort**, not machine runtime. Actual runtime depends on DEM size/resolution, number of observers, number of sites, hardware, GPU configuration, target density, and ArcGIS settings.
