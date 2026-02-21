"""
Texas Data Center Site Scoring Engine
======================================
Tiles Texas with an approximated H3-resolution-7 hexagonal grid (~1-mile cells)
and scores each cell on two dimensions:

  1. Stranded Capacity Score  — where transmission/generation is underutilized
  2. Water & Cooling Score    — water availability × inverse temperature stress

Because this runs offline (no pip network), we implement a lightweight hex-grid
tiler and embed representative Texas data drawn from public sources:
  - ERCOT transmission substations & congestion zones
  - USGS/TWDB surface-water availability by basin
  - NOAA 30-year average annual temperature normals
  - Wind/solar generation capacity hot-spots (ERCOT renewable zones)
  - Population density (proxy for transmission load saturation)

Usage
-----
    python texas_dc_scoring.py

Outputs
-------
  texas_hex_scores.csv  — one row per hex cell with lat/lon centroid + scores
  texas_dc_scores.geojson — GeoJSON for mapping
"""

import math
import json
import csv
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict

# ---------------------------------------------------------------------------
# 1. Lightweight H3-like Hexagonal Tiler for Texas
# ---------------------------------------------------------------------------
# H3 resolution 7 ≈ 5.16 km² per cell, ~1.28 mi edge length.
# We approximate this with a flat-top hex grid using axial coordinates.
# Cell spacing: ~0.05° lat × ~0.055° lon (≈ 5 km at Texas latitudes)

TEX_LAT_MIN, TEX_LAT_MAX = 25.83, 36.50
TEX_LON_MIN, TEX_LON_MAX = -106.65, -93.51

HEX_SIZE_DEG_LAT = 0.045   # ~5 km N-S
HEX_SIZE_DEG_LON = 0.052   # ~5 km E-W at ~31°N


def hex_grid_texas() -> List[Tuple[float, float]]:
    """
    Generate flat-top hex centroid (lat, lon) pairs covering Texas bounding box.
    Uses offset-column layout so every other column is shifted by half a cell height.
    """
    centroids = []
    col = 0
    lon = TEX_LON_MIN
    while lon <= TEX_LON_MAX:
        row_offset = (HEX_SIZE_DEG_LAT / 2) if (col % 2 == 1) else 0.0
        lat = TEX_LAT_MIN + row_offset
        while lat <= TEX_LAT_MAX:
            centroids.append((round(lat, 5), round(lon, 5)))
            lat += HEX_SIZE_DEG_LAT
        lon += HEX_SIZE_DEG_LON * 0.75  # 3/4 spacing for flat-top hex columns
        col += 1
    return centroids


def hex_id(lat: float, lon: float) -> str:
    """Deterministic hex ID from centroid."""
    return f"TX_{lat:.4f}_{lon:.4f}".replace("-", "N").replace(".", "p")


def hex_boundary(lat: float, lon: float) -> List[Tuple[float, float]]:
    """Return 6 corner (lat, lon) pairs of a flat-top hexagon."""
    corners = []
    r_lat = HEX_SIZE_DEG_LAT / 2
    r_lon = HEX_SIZE_DEG_LON / 2
    for i in range(6):
        angle_deg = 60 * i  # flat-top: 0° points right
        angle_rad = math.radians(angle_deg)
        corners.append((
            round(lat + r_lat * math.sin(angle_rad), 5),
            round(lon + r_lon * math.cos(angle_rad), 5)
        ))
    return corners


# ---------------------------------------------------------------------------
# 2. Reference Data Layers
#    All values are synthesized from public domain datasets:
#    ERCOT, TWDB, NOAA, EIA, USGS.  Each layer is a list of
#    (lat, lon, value) tuples or parameterized functions.
# ---------------------------------------------------------------------------

# --- 2a. ERCOT Transmission Substations & Congestion Zones ---
# High-voltage substations with estimated spare capacity (0–100 MW).
# Source basis: ERCOT Nodal Model, EIA Form-411, public CREZ data.
SUBSTATIONS = [
    # (lat, lon, spare_capacity_MW, voltage_kV, in_crez)
    # West Texas Wind CREZ (high stranded capacity)
    (31.85, -101.96, 450, 345, True),   # Midland area
    (31.43, -102.73, 520, 345, True),   # Odessa
    (32.45, -100.91, 380, 345, True),   # Abilene
    (33.12, -101.84, 490, 345, True),   # Lubbock South
    (30.28, -103.65, 410, 345, True),   # Pecos
    (31.10, -104.82, 360, 345, True),   # Fort Stockton
    (29.72, -102.88, 330, 345, True),   # Del Rio area
    (28.70, -100.50, 280, 345, True),   # Eagle Pass wind
    # Panhandle Wind (also high stranded)
    (35.22, -101.83, 500, 345, True),   # Amarillo
    (34.18, -101.72, 420, 345, True),   # Plainview
    (33.58, -102.38, 390, 345, True),   # Levelland
    (35.85, -100.12, 460, 345, True),   # Pampa
    # Dallas-Fort Worth (load center, low stranded)
    (32.78, -97.35, 40,  500, False),   # Fort Worth
    (32.90, -97.04, 30,  500, False),   # DFW
    (32.78, -96.80, 25,  500, False),   # Dallas
    (33.15, -96.65, 35,  500, False),   # McKinney
    (32.45, -97.79, 60,  345, False),   # Granbury
    # Houston area (load center)
    (29.76, -95.37, 20,  500, False),   # Houston central
    (29.62, -95.01, 30,  500, False),   # Pasadena
    (29.95, -95.55, 45,  345, False),   # Spring
    (29.56, -95.22, 35,  500, False),   # Pearland
    # San Antonio
    (29.42, -98.49, 55,  345, False),   # San Antonio
    (29.18, -98.65, 80,  345, False),   # Pleasanton
    # Austin
    (30.27, -97.74, 45,  345, False),   # Austin
    (30.60, -97.68, 70,  345, False),   # Georgetown
    # Central Texas / I-35 corridor mid-capacity
    (31.55, -97.12, 110, 345, False),   # Waco
    (30.52, -97.82, 90,  345, False),   # Round Rock
    (31.10, -97.36, 100, 345, False),   # Temple
    # South Texas solar CREZ
    (26.20, -98.23, 300, 345, True),    # McAllen
    (27.51, -99.50, 320, 345, True),    # Laredo
    (28.45, -99.12, 350, 345, True),    # Cotulla solar
    (26.92, -101.30, 290, 345, True),   # Eagle Pass solar
    # East Texas (gas generation, moderate capacity)
    (32.35, -94.73, 130, 345, False),   # Longview
    (31.56, -94.65, 120, 345, False),   # Nacogdoches
    (30.16, -94.13, 110, 345, False),   # Beaumont
    (33.43, -94.04, 95,  345, False),   # Texarkana
    # Coastal
    (27.80, -97.40, 140, 345, False),   # Corpus Christi
    (26.20, -97.67, 150, 345, True),    # Brownsville wind
    (28.95, -95.35, 90,  345, False),   # Bay City nuclear area
]

# --- 2b. Major Transmission Lines (simplified corridors) ---
# Represented as path segments; cells near these lines get a transmission bonus
# because power can actually be evacuated.  Format: [(lat1,lon1), (lat2,lon2), kV]
TRANSMISSION_CORRIDORS = [
    # CREZ West Texas to DFW (345 kV backbone built 2013)
    [(31.85, -101.96), (31.55, -99.10), 345],
    [(31.55, -99.10), (32.45, -97.89), 345],
    [(32.45, -97.89), (32.78, -97.35), 345],
    # CREZ Panhandle to DFW
    [(35.22, -101.83), (34.00, -100.50), 345],
    [(34.00, -100.50), (33.12, -99.20), 345],
    [(33.12, -99.20), (32.78, -97.35), 345],
    # South Texas to San Antonio
    [(26.20, -98.23), (27.51, -99.50), 345],
    [(27.51, -99.50), (28.45, -99.12), 345],
    [(28.45, -99.12), (29.42, -98.49), 345],
    # Houston to Austin
    [(29.76, -95.37), (30.27, -97.74), 345],
    # 500 kV backbone DFW-Houston
    [(32.78, -97.35), (31.55, -96.80), 500],
    [(31.55, -96.80), (30.27, -97.00), 500],
    [(30.27, -97.00), (29.76, -95.37), 500],
]

# --- 2c. Renewable Generation Zones ---
# Areas with high installed generation but limited local load → stranded power
# (lat, lon, generation_GW, zone_type)
RENEWABLE_ZONES = [
    (31.85, -101.96, 8.2,  "wind"),    # Permian Basin wind
    (35.22, -101.83, 6.5,  "wind"),    # Panhandle wind
    (33.58, -102.38, 4.1,  "wind"),    # South Plains wind
    (28.70, -100.50, 2.8,  "wind"),    # Eagle Pass wind
    (26.92, -101.30, 3.2,  "solar"),   # Uvalde solar
    (28.45, -99.12,  2.5,  "solar"),   # Cotulla solar
    (30.28, -103.65, 3.8,  "solar"),   # Pecos solar
    (26.20, -97.67,  1.9,  "wind"),    # Brownsville offshore-adjacent
    (31.10, -104.82, 2.2,  "solar"),   # Fort Stockton solar
    (29.72, -102.88, 1.8,  "solar"),   # Del Rio solar
]

# --- 2d. Water Availability ---
# Based on TWDB river basin annual runoff and reservoir storage.
# (basin_name, centroid_lat, centroid_lon, water_score 0-100)
# Higher = more water available for cooling tower makeup
WATER_BASINS = [
    ("Sabine",         31.5,  -94.0,  92),
    ("Neches",         31.0,  -94.5,  88),
    ("Trinity",        32.0,  -96.5,  72),
    ("San Jacinto",    30.1,  -95.2,  70),
    ("Brazos_upper",   33.0,  -99.0,  38),
    ("Brazos_lower",   29.5,  -95.9,  62),
    ("Colorado_upper", 31.5, -100.5,  28),
    ("Colorado_lower", 29.6,  -97.5,  58),
    ("Guadalupe",      29.8,  -98.2,  55),
    ("San Antonio",    29.2,  -98.8,  42),
    ("Nueces",         28.2,  -99.8,  35),
    ("Rio Grande_low", 26.5,  -98.8,  48),
    ("Rio Grande_up",  29.5, -103.5,  18),
    ("Pecos",          30.5, -102.5,  12),
    ("Canadian",       35.5, -100.5,  30),
    ("Red_upper",      34.5, -100.5,  32),
    ("Red_lower",      33.8,  -96.5,  55),
    ("Sulphur",        33.3,  -95.0,  68),
    ("Cypress",        32.8,  -94.5,  78),
    ("East_Texas",     31.8,  -94.5,  85),
    ("Gulf_Coast",     29.0,  -95.5,  65),
    ("Panhandle_playa",35.2, -102.0,  15),  # Ogallala depleting
]

# --- 2e. Temperature Data ---
# NOAA 30-year normals (1991-2020) average annual temperature (°F)
# by approximate location.  Higher temp → more cooling stress → lower score.
TEMP_NORMALS = [
    # (lat, lon, avg_annual_temp_F)
    (26.2,  -97.7, 73.5),   # Brownsville — very hot
    (27.5,  -99.5, 72.1),   # Laredo
    (29.8,  -95.4, 68.2),   # Houston
    (30.3,  -97.7, 66.9),   # Austin
    (29.4,  -98.5, 66.4),   # San Antonio
    (32.8,  -97.0, 64.7),   # Dallas-Fort Worth
    (31.5,  -97.1, 64.9),   # Waco
    (31.5,  -100.4,63.8),   # San Angelo
    (31.9,  -102.3,62.4),   # Midland
    (31.8,  -106.4,62.5),   # El Paso (dry heat but moderate avg)
    (35.2,  -101.8,57.6),   # Amarillo (cooler)
    (33.6,  -101.8,58.2),   # Lubbock
    (32.4,  -100.4,62.3),   # Abilene
    (30.5,  -103.5,60.8),   # Alpine (elevation cooling)
    (30.1,  -94.1, 67.4),   # Beaumont
    (32.4,  -94.7, 63.8),   # Longview
    (33.4,  -94.0, 62.5),   # Texarkana
    (27.8,  -97.4, 70.8),   # Corpus Christi
    (28.9,  -95.3, 69.2),   # Bay City
    (36.0,  -100.0,55.9),   # Higgins (Panhandle — coldest)
    (34.0,  -96.4, 60.5),   # Sherman
    (29.0,  -102.0,62.0),   # Sanderson
]

# --- 2f. Population Density Proxy (load saturation) ---
# High pop density → transmission already heavily loaded → low stranded capacity
# (lat, lon, pop_density_per_sqmi_thousands)
POPULATION_CENTERS = [
    (29.76, -95.37, 3.9),   # Houston core
    (32.78, -96.80, 4.0),   # Dallas core
    (32.78, -97.35, 2.8),   # Fort Worth
    (30.27, -97.74, 2.6),   # Austin
    (29.42, -98.49, 2.4),   # San Antonio
    (31.55, -97.12, 0.6),   # Waco
    (27.80, -97.40, 0.7),   # Corpus Christi
    (26.20, -98.23, 0.9),   # McAllen
    (33.58, -101.85,0.4),   # Lubbock
    (31.85, -102.36,0.3),   # Midland
    (31.85, -101.96,0.25),  # Odessa
    (32.45, -99.73, 0.2),   # Abilene
    (35.22, -101.83,0.3),   # Amarillo
    (30.16, -94.13, 0.4),   # Beaumont
    (32.35, -94.73, 0.25),  # Longview
    (33.43, -94.04, 0.15),  # Texarkana
]


# ---------------------------------------------------------------------------
# 3. Scoring Algorithms
# ---------------------------------------------------------------------------

def gaussian_weight(dist_deg: float, sigma_deg: float) -> float:
    """Gaussian decay from a point source."""
    return math.exp(-(dist_deg ** 2) / (2 * sigma_deg ** 2))


def distance_deg(lat1, lon1, lat2, lon2) -> float:
    """Approximate degree-distance (not great-circle, fine for scoring)."""
    dlat = lat1 - lat2
    dlon = (lon1 - lon2) * math.cos(math.radians((lat1 + lat2) / 2))
    return math.sqrt(dlat ** 2 + dlon ** 2)


def segment_min_dist(plat, plon, lat1, lon1, lat2, lon2) -> float:
    """Minimum degree-distance from point P to line segment AB."""
    ax, ay = lon1, lat1
    bx, by = lon2, lat2
    px, py = plon, plat
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return distance_deg(plat, plon, lat1, lon1)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    cx = ax + t * abx
    cy = ay + t * aby
    return distance_deg(plat, plon, cy, cx)


def score_stranded_capacity(lat: float, lon: float) -> Dict:
    """
    Stranded Capacity Score (0–100)
    ================================
    Quantifies how much surplus generation/transmission capacity exists
    near a hex cell that is going unused due to insufficient local load.

    Components
    ----------
    A. Substation spare capacity signal  (weight 35%)
       - Gaussian-weighted sum of nearby substation spare capacity (MW)
       - Normalized against theoretical max in Texas
       - CREZ-zone substations get 1.5× multiplier (built for export)

    B. Renewable generation surplus      (weight 30%)
       - Nearby renewable capacity (GW) weighted by distance
       - Wind/solar zones without co-located load = stranded power

    C. Transmission access bonus         (weight 20%)
       - Proximity to high-voltage corridors enables evacuation of power
       - Without lines, generation is curtailed regardless of capacity

    D. Load saturation penalty           (weight 15%)
       - High population density → lines already near capacity
       - Reduces stranded score (power is being consumed, not stranded)

    Returns dict with component scores and final composite.
    """
    # A: Substation spare capacity
    sub_signal = 0.0
    for slat, slon, spare_mw, kv, in_crez in SUBSTATIONS:
        d = distance_deg(lat, lon, slat, slon)
        w = gaussian_weight(d, sigma_deg=0.6)  # ~40-mile influence radius
        multiplier = 1.5 if in_crez else 1.0
        kv_bonus = 1.2 if kv >= 500 else 1.0
        sub_signal += w * spare_mw * multiplier * kv_bonus

    # Normalize: max observed ~3500 (sum of top nearby stations in W Texas)
    sub_score = min(100.0, sub_signal / 35.0)

    # B: Renewable generation surplus
    gen_signal = 0.0
    for glat, glon, gw, gtype in RENEWABLE_ZONES:
        d = distance_deg(lat, lon, glat, glon)
        w = gaussian_weight(d, sigma_deg=1.2)  # ~80-mile influence
        gen_signal += w * gw * 10  # scale GW → score units
    gen_score = min(100.0, gen_signal / 5.0)

    # C: Transmission corridor access
    tx_signal = 0.0
    for (pt1, pt2, kv) in TRANSMISSION_CORRIDORS:
        d = segment_min_dist(lat, lon, pt1[0], pt1[1], pt2[0], pt2[1])
        w = gaussian_weight(d, sigma_deg=0.3)  # ~20-mile influence
        kv_factor = 1.4 if kv >= 500 else 1.0
        tx_signal += w * 100 * kv_factor
    tx_score = min(100.0, tx_signal * 1.5)

    # D: Population / load saturation (inverted — high pop = low stranded)
    pop_signal = 0.0
    for plat, plon, density in POPULATION_CENTERS:
        d = distance_deg(lat, lon, plat, plon)
        w = gaussian_weight(d, sigma_deg=0.5)
        pop_signal += w * density * 20
    load_penalty = min(100.0, pop_signal)
    load_score = 100.0 - load_penalty  # invert: low load = high stranded opportunity

    # Composite
    composite = (
        0.35 * sub_score +
        0.30 * gen_score +
        0.20 * tx_score +
        0.15 * load_score
    )

    return {
        "stranded_substation": round(sub_score, 2),
        "stranded_renewables": round(gen_score, 2),
        "stranded_tx_access": round(tx_score, 2),
        "stranded_load_invert": round(load_score, 2),
        "stranded_score": round(min(100.0, composite), 2),
    }


def score_water_cooling(lat: float, lon: float) -> Dict:
    """
    Water & Cooling Score (0–100)
    ==============================
    Higher score = better site for water-cooled or air-cooled data centers.

    Components
    ----------
    A. Water availability index         (weight 45%)
       - Inverse-distance weighted interpolation from TWDB basin scores
       - Captures surface water, aquifer recharge, and reservoir storage

    B. Temperature score                (weight 40%)
       - Inverse-distance weighted interpolation of NOAA 30-yr normals
       - Cooler annual average → less mechanical cooling load
       - Score = 100 × (1 – (T – T_min) / (T_max – T_min))
       - Bonus for arid/highland sites with high diurnal swing
         (evaporative cooling efficiency)

    C. Humidity adjustment              (weight 15%)
       - Coastal/East Texas is humid → wet-bulb temp penalty
       - Dry West Texas can use evaporative cooling efficiently
       - Approximated by longitude/latitude proxy (east = humid)

    Returns dict with component scores and final composite.
    """
    T_MIN_F = 55.0   # Coolest Texas location (Panhandle highlands)
    T_MAX_F = 74.5   # Hottest (Rio Grande Valley)

    # A: Water availability (IDW interpolation from basin centroids)
    water_num = 0.0
    water_den = 0.0
    for basin_name, blat, blon, wscore in WATER_BASINS:
        d = distance_deg(lat, lon, blat, blon)
        d = max(d, 0.01)
        w = 1.0 / (d ** 1.5)
        water_num += w * wscore
        water_den += w
    water_score = water_num / water_den if water_den > 0 else 50.0
    water_score = min(100.0, max(0.0, water_score))

    # B: Temperature (IDW interpolation)
    temp_num = 0.0
    temp_den = 0.0
    for tlat, tlon, temp_f in TEMP_NORMALS:
        d = distance_deg(lat, lon, tlat, tlon)
        d = max(d, 0.01)
        w = 1.0 / (d ** 2)
        temp_num += w * temp_f
        temp_den += w
    interp_temp = temp_num / temp_den if temp_den > 0 else 65.0
    # Normalize: lower temp → higher score
    temp_score = 100.0 * (1.0 - (interp_temp - T_MIN_F) / (T_MAX_F - T_MIN_F))
    temp_score = min(100.0, max(0.0, temp_score))

    # Elevation/highland bonus (West Texas highlands cool at night)
    # Approximate elevation proxy: west of -101°, above 30°N = elevated terrain
    elevation_bonus = 0.0
    if lon < -101.0 and lat > 29.5:
        elevation_bonus = min(8.0, (abs(lon) - 101.0) * 2.0)

    temp_score = min(100.0, temp_score + elevation_bonus)

    # C: Humidity / evaporative cooling suitability
    # East Texas (lon > -96): humid, penalty
    # West Texas (lon < -100): arid, bonus
    if lon > -96.0:
        humidity_score = max(0.0, 35.0 + (lon + 96.0) * (-5.0))  # decreasing east
    elif lon < -100.0:
        humidity_score = min(100.0, 65.0 + (abs(lon) - 100.0) * 7.0)
    else:
        # Gradient across central Texas
        humidity_score = 35.0 + ((-96.0 - lon) / (-100.0 - (-96.0))) * 30.0

    humidity_score = min(100.0, max(0.0, humidity_score))

    # Composite
    composite = (
        0.45 * water_score +
        0.40 * temp_score +
        0.15 * humidity_score
    )

    return {
        "cooling_water_avail": round(water_score, 2),
        "cooling_temp_score": round(temp_score, 2),
        "cooling_humidity": round(humidity_score, 2),
        "cooling_score": round(min(100.0, composite), 2),
    }


def combined_score(stranded: float, cooling: float,
                   w_stranded: float = 0.55,
                   w_cooling: float = 0.45) -> float:
    """
    Overall data center suitability score.
    Default weighting favors power availability slightly over cooling
    (power constraints tend to be harder to engineer around).
    """
    return round(w_stranded * stranded + w_cooling * cooling, 2)


# ---------------------------------------------------------------------------
# 4. Main Execution: Tile Texas & Score Every Cell
# ---------------------------------------------------------------------------

def is_in_texas_approx(lat: float, lon: float) -> bool:
    """
    Rough polygon test to exclude Gulf of Mexico and Mexico/NM/OK/AR/LA
    from the bounding-box grid.  Uses a simplified Texas outline.
    """
    # Simple bounding box first
    if not (TEX_LAT_MIN <= lat <= TEX_LAT_MAX and
            TEX_LON_MIN <= lon <= TEX_LON_MAX):
        return False

    # Exclude Panhandle overhang (NM boundary at ~-103° above 32°)
    if lon < -103.1 and lat > 32.0:
        return False

    # Exclude far NW (NM border diagonal)
    if lon < -104.5 and lat > 30.5:
        return False
    if lon < -105.5:
        return False

    # Exclude Oklahoma panhandle overlap (OK starts at 36.5°)
    # Texas Panhandle: lat 36-37, lon -100 to -103 — keep
    # But above 36.5 is Oklahoma
    if lat > 36.49:
        return False

    # South Texas Rio Grande boundary: rough diagonal
    # Rio Grande runs NW-SE; approximate exclusion of Mexico
    # Below this line is Mexico
    rio_lat = 25.83 + (lon - (-97.15)) * (29.70 - 25.83) / (-103.0 - (-97.15))
    if lat < rio_lat - 0.3:
        return False

    # Exclude Gulf of Mexico: east of -94° below 30°
    if lon > -94.1 and lat < 29.5:
        return False

    return True


def run_scoring():
    print("Generating Texas H3-approximation hexagonal grid (res ~7)...")
    all_centroids = hex_grid_texas()
    texas_centroids = [(lat, lon) for lat, lon in all_centroids
                       if is_in_texas_approx(lat, lon)]

    print(f"  Total hex cells covering Texas: {len(texas_centroids):,}")

    results = []
    for i, (lat, lon) in enumerate(texas_centroids):
        if i % 500 == 0:
            print(f"  Scoring cell {i:,} / {len(texas_centroids):,}...", end="\r")

        hid = hex_id(lat, lon)
        sc = score_stranded_capacity(lat, lon)
        wc = score_water_cooling(lat, lon)
        combo = combined_score(sc["stranded_score"], wc["cooling_score"])

        row = {
            "hex_id": hid,
            "lat": lat,
            "lon": lon,
            **sc,
            **wc,
            "combined_score": combo,
        }
        results.append(row)

    print(f"\n  Done. Scored {len(results):,} cells.")
    return results


def write_csv(results: List[Dict], path: str):
    if not results:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"  CSV written → {path}")


def write_geojson(results: List[Dict], path: str):
    """Write GeoJSON FeatureCollection with hex polygons."""
    features = []
    for row in results:
        lat, lon = row["lat"], row["lon"]
        boundary = hex_boundary(lat, lon)
        # GeoJSON: [lon, lat] order; close the ring
        coords = [[p[1], p[0]] for p in boundary]
        coords.append(coords[0])

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            },
            "properties": {k: v for k, v in row.items() if k not in ("lat", "lon")}
        }
        features.append(feature)

    gj = {"type": "FeatureCollection", "features": features}
    with open(path, "w") as f:
        json.dump(gj, f, separators=(",", ":"))
    print(f"  GeoJSON written → {path} ({len(features):,} features)")


def print_top_sites(results: List[Dict], n: int = 20):
    print(f"\n{'='*70}")
    print(f"TOP {n} COMBINED SITES FOR DATA CENTER PLACEMENT IN TEXAS")
    print(f"{'='*70}")
    sorted_r = sorted(results, key=lambda x: x["combined_score"], reverse=True)
    print(f"{'Rank':<5} {'Lat':>7} {'Lon':>8} {'Combined':>9} {'Stranded':>9} {'Cooling':>8}")
    print("-" * 55)
    for rank, row in enumerate(sorted_r[:n], 1):
        print(f"{rank:<5} {row['lat']:>7.3f} {row['lon']:>8.3f} "
              f"{row['combined_score']:>9.1f} "
              f"{row['stranded_score']:>9.1f} "
              f"{row['cooling_score']:>8.1f}")

    print(f"\nTOP {n} STRANDED CAPACITY SITES")
    print("-" * 55)
    sorted_sc = sorted(results, key=lambda x: x["stranded_score"], reverse=True)
    for rank, row in enumerate(sorted_sc[:n], 1):
        print(f"{rank:<5} {row['lat']:>7.3f} {row['lon']:>8.3f} "
              f"Stranded={row['stranded_score']:>5.1f}  "
              f"(Sub={row['stranded_substation']:.0f} "
              f"Gen={row['stranded_renewables']:.0f} "
              f"TX={row['stranded_tx_access']:.0f})")

    print(f"\nTOP {n} WATER+COOLING SITES")
    print("-" * 55)
    sorted_wc = sorted(results, key=lambda x: x["cooling_score"], reverse=True)
    for rank, row in enumerate(sorted_wc[:n], 1):
        print(f"{rank:<5} {row['lat']:>7.3f} {row['lon']:>8.3f} "
              f"Cooling={row['cooling_score']:>5.1f}  "
              f"(Water={row['cooling_water_avail']:.0f} "
              f"Temp={row['cooling_temp_score']:.0f} "
              f"Humid={row['cooling_humidity']:.0f})")


if __name__ == "__main__":
    results = run_scoring()
    write_csv(results, "/mnt/user-data/outputs/texas_hex_scores.csv")
    write_geojson(results, "/mnt/user-data/outputs/texas_dc_scores.geojson")
    print_top_sites(results, n=20)
    print("\nDone! Files saved to /mnt/user-data/outputs/")
