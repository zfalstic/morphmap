Here's a full summary of everything we've covered:

---

## Project: Energy Surplus Heatmap Tool for Data Center Site Selection

### Core Concept
Build an algorithm that identifies geographic areas with excess power grid capacity — where generation exceeds demand. The primary market is data center developers and site selection consultants who need high-power locations.

### Current Scope
Scaled down to **Texas (ERCOT grid)** as the starting point, with the goal of producing a heatmap at the highest possible geographic resolution showing where excess capacity exists.

---

## Data Sources

**Supply Side**
- EIA Form 860 — every generator in Texas, GPS coordinates, nameplate capacity (MW), fuel type
- ERCOT generation data by weather zone

**Demand Side**
- U.S. Census tracts — population-based residential demand (~10,500 kWh/year per capita)
- County Business Patterns (Census) — commercial/industrial business counts by NAICS code
- ERCOT historical load data by weather zone (8 zones in Texas)
- EIA CBECS — average kWh consumption benchmarks by business type

**Grid Infrastructure**
- HIFLD — transmission line locations, substation locations and capacity
- ERCOT congestion and substation capacity data

**Land Use**
- NLCD (National Land Cover Database)
- Microsoft Building Footprints

---

## Algorithm Design

**Geographic Grid**
- Uber's H3 hexagonal grid at resolution 7 (~1 mile cells)
- Tiles Texas completely with no gaps or overlaps
- Every data source gets spatially joined to H3 cell ID as the common key

**Net Energy Calculation**
```
net[cell] = supply_mwh - demand_mwh

supply_mwh = nameplate_mw * capacity_factor * 8760
demand_mwh = residential_demand + commercial_demand
```

**Capacity Factors by Fuel Type**
- Nuclear: 0.92
- Natural Gas: 0.57
- Coal: 0.49
- Hydro: 0.42
- Wind: 0.35
- Solar: 0.25

**Composite Score Components**
- Surplus Score (40%) — net MWh per cell
- Stability Score (25%) — baseload vs. intermittent fuel mix
- Grid Infrastructure Score (20%) — proximity to high-voltage transmission and substations
- Cost/LMP Score (15%) — locational marginal prices as cost proxy

All components normalized 0-100 and combined into a weighted composite score.

---

## Pipeline Architecture

```
EIA 860 (generators)
Census + CBP (demand)      →  Per-layer computation  →  JOIN on H3 cell  →  Score table
HIFLD (grid infrastructure)
ERCOT (load/LMP data)
```

Each layer is computed independently and joined by H3 cell ID. Final scoring job runs downstream of all layers. Orchestrated with Apache Airflow.

---

## Storage
- PostgreSQL + PostGIS
- Spatial indexing enables fast queries like "top 20 cells in Texas by score"
- ~3.5M cells nationally, far fewer for Texas alone

---

## Product Vision (Full Scale)
- Interactive heatmap UI (Mapbox GL JS or Deck.gl)
- Filter by state/city, minimum surplus threshold, fuel type preference
- Sort by composite score or individual components
- Site scorecard PDF export (premium feature)
- Alerts when regional scores change significantly
- Forward-looking ML predictions using XGBoost/LightGBM trained on historical EIA data

---

## Tech Stack
| Layer | Tool |
|---|---|
| Data pipeline | Python, Apache Airflow |
| Geospatial processing | GeoPandas, H3, PostGIS |
| ML | XGBoost, scikit-learn |
| Backend | FastAPI |
| Frontend map | Mapbox GL JS or Deck.gl |
| Database | PostgreSQL + PostGIS |
| Hosting | AWS or GCP |

---

## Immediate Next Step
Build the Texas pipeline end to end:
1. Pull EIA 860 for Texas generators
2. Assign each generator to an H3 cell
3. Pull Census demand data per tract, join to H3
4. Pull ERCOT load data for calibration
5. Compute net score per cell
6. Visualize as heatmap
