import * as h3 from "h3-js";

// Texas bounding polygon — h3-js v4 requires [lat, lng] order
const TEXAS_POLYGON = [
  [31.901, -106.645646],
  [31.784, -106.528879],
  [31.562, -106.277244],
  [30.84,  -105.4],
  [29.672, -104.977665],
  [29.45,  -104.561],
  [28.98,  -103.941],
  [28.97,  -103.118],
  [29.76,  -102.48],
  [29.77,  -101.66],
  [28.19,  -100.96],
  [28.17,  -100.11],
  [27.66,  -99.93],
  [27.02,  -99.44],
  [26.38,  -99.45],
  [26.43,  -99.1],
  [26.07,  -98.08],
  [25.87,  -97.36],
  [25.97,  -97.14],
  [26.06,  -97.02],
  [28.3,   -96.7],
  [28.6,   -96.8],
  [28.97,  -95.96],
  [29.08,  -94.74],
  [29.72,  -93.84],
  [30.05,  -93.93],
  [30.13,  -93.7],
  [31.0,   -93.7],
  [31.56,  -93.52],
  [33.0,   -93.53],
  [33.552, -94.043],
  [33.638, -94.484],
  [33.937, -95.154],
  [33.778, -96.0],
  [33.985, -96.66],
  [33.853, -97.46],
  [34.0,   -98.0],
  [34.21,  -98.95],
  [34.41,  -99.57],
  [34.56,  -100.0],
  [36.5,   -100.0],
  [36.5,   -103.0],
  [32.0,   -103.0],
  [31.901, -106.645646],
];

// ─── Supply Sources ────────────────────────────────────────────────────────────
// radLat / radLng allow anisotropic Gaussians (elongated shapes for wind corridors)
const SUPPLY_SOURCES = [
  // ── Wind ──────────────────────────────────────────────────────────────────
  // Panhandle wind cluster (Great Plains / Hansford / Ochiltree) — biggest in state
  { lat: 36.1,   lng: -101.5,  weight: 0.98, radLat: 1.4, radLng: 2.2 },
  // Roscoe / West Texas wind corridor (Nolan, Mitchell, Scurry counties)
  { lat: 32.264, lng: -100.344, weight: 0.95, radLat: 2.5, radLng: 1.2 },
  // Big Spring / Howard County wind belt
  { lat: 32.25,  lng: -101.5,  weight: 0.75, radLat: 1.8, radLng: 1.0 },
  // South Texas coastal wind — Los Vientos (Starr / Willacy counties)
  { lat: 26.5,   lng: -97.5,   weight: 0.75, radLat: 0.8, radLng: 1.4 },
  // Corpus Christi coastal wind
  { lat: 28.1,   lng: -97.4,   weight: 0.55, radLat: 0.7, radLng: 1.1 },

  // ── Nuclear ───────────────────────────────────────────────────────────────
  // Comanche Peak (Glen Rose, Somervell County) — tight high spike
  { lat: 32.298, lng: -97.786, weight: 1.0,  radLat: 0.45, radLng: 0.45 },
  // South Texas Nuclear Project (Bay City, Matagorda County)
  { lat: 28.795, lng: -96.048, weight: 1.0,  radLat: 0.45, radLng: 0.45 },

  // ── Natural Gas ───────────────────────────────────────────────────────────
  // GW Ranch / Fort Stockton mega-cluster (Pecos County) — emerging
  { lat: 31.8,   lng: -103.2,  weight: 0.85, radLat: 1.5, radLng: 1.5 },
  // Permian Basin gas generation (Midland/Odessa corridor)
  { lat: 31.9,   lng: -102.1,  weight: 0.72, radLat: 1.2, radLng: 1.2 },
  // Fermi America Panhandle gas cluster (Carson County, NE of Amarillo)
  { lat: 35.22,  lng: -101.8,  weight: 0.88, radLat: 1.0, radLng: 1.0 },

  // ── Coal (East Texas lignite belt) ────────────────────────────────────────
  // Martin Lake Steam Electric (Rusk County)
  { lat: 32.261, lng: -94.565, weight: 0.88, radLat: 0.6, radLng: 0.6 },
  // General East Texas lignite belt
  { lat: 32.1,   lng: -94.5,   weight: 0.72, radLat: 1.8, radLng: 0.8 },

  // ── Utility-Scale Solar ───────────────────────────────────────────────────
  // Prospero Solar (Andrews County, NW of Odessa)
  { lat: 32.314, lng: -102.51, weight: 0.60, radLat: 0.9, radLng: 0.9 },
  // McCamey / Pecos County solar (Taygete)
  { lat: 31.05,  lng: -103.7,  weight: 0.48, radLat: 0.8, radLng: 0.8 },
  // West Texas solar growth zone (general Andrews / Winkler / Ward counties)
  { lat: 31.5,   lng: -103.0,  weight: 0.65, radLat: 1.8, radLng: 1.4 },
];

// ─── Demand Sinks ──────────────────────────────────────────────────────────────
// These subtract from the raw score — cities consume more than nearby generation
const DEMAND_SINKS = [
  { lat: 29.749, lng: -95.358,  weight: -1.0,  radLat: 1.4, radLng: 1.4 }, // Houston
  { lat: 32.779, lng: -96.809,  weight: -0.95, radLat: 1.1, radLng: 1.1 }, // Dallas
  { lat: 32.725, lng: -97.321,  weight: -0.80, radLat: 0.9, radLng: 0.9 }, // Fort Worth
  { lat: 29.424, lng: -98.491,  weight: -0.92, radLat: 1.1, radLng: 1.1 }, // San Antonio
  { lat: 30.267, lng: -97.743,  weight: -0.85, radLat: 0.9, radLng: 0.9 }, // Austin
  { lat: 31.772, lng: -106.461, weight: -0.65, radLat: 0.7, radLng: 0.7 }, // El Paso
  { lat: 27.801, lng: -97.396,  weight: -0.50, radLat: 0.6, radLng: 0.6 }, // Corpus Christi
  { lat: 31.923, lng: -102.222, weight: -0.52, radLat: 0.6, radLng: 0.6 }, // Midland/Odessa
  { lat: 33.577, lng: -101.855, weight: -0.48, radLat: 0.55,radLng: 0.55 },// Lubbock
  { lat: 35.222, lng: -101.831, weight: -0.48, radLat: 0.55,radLng: 0.55 },// Amarillo
  { lat: 30.068, lng: -94.130,  weight: -0.40, radLat: 0.6, radLng: 0.6 }, // Beaumont/Port Arthur
  { lat: 31.549, lng: -97.147,  weight: -0.35, radLat: 0.5, radLng: 0.5 }, // Waco
  { lat: 32.735, lng: -97.108,  weight: -0.35, radLat: 0.5, radLng: 0.5 }, // Arlington
];

function anisotropicGaussian(cellLat, cellLng, source) {
  const dlat = cellLat - source.lat;
  const dlng = cellLng - source.lng;
  return (
    source.weight *
    Math.exp(
      -((dlat * dlat) / (2 * source.radLat * source.radLat) +
        (dlng * dlng) / (2 * source.radLng * source.radLng))
    )
  );
}

// Seeded pseudo-random for reproducibility
function seededRandom(seed) {
  let s = seed;
  return function () {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

// Texas lat/lng bounds
const LAT_MIN = 25.8, LAT_MAX = 36.5;
const LNG_MIN = -106.6, LNG_MAX = -93.5;

export function generateTexasTemperatureData(resolution = 5) {
  const cells = h3.polygonToCells(TEXAS_POLYGON, resolution);
  const rand = seededRandom(99);

  return cells.map((h3Index) => {
    const [lat, lng] = h3.cellToLatLng(h3Index);

    // N-S gradient: south is hotter (lat_norm=0 at south, 1 at north)
    const latNorm = (lat - LAT_MIN) / (LAT_MAX - LAT_MIN);
    // W-E gradient: west (desert) is slightly hotter
    const lngNorm = (lng - LNG_MIN) / (LNG_MAX - LNG_MIN);

    const base = 0.65 * (1 - latNorm) + 0.20 * (1 - lngNorm);
    const noise = (rand() - 0.5) * 0.12;
    const score = Math.max(0, Math.min(1, base + noise));

    // Map score to Fahrenheit: 65°F (cool Panhandle) → 115°F (hot South Texas)
    const tempF = Math.round(65 + score * 50);

    return { h3Index, score, tempF };
  });
}

export function generateTexasHexData(resolution = 5) {
  const cells = h3.polygonToCells(TEXAS_POLYGON, resolution);
  const rand = seededRandom(42);

  // First pass: compute raw scores to determine normalization range
  const rawScores = cells.map((h3Index) => {
    const [lat, lng] = h3.cellToLatLng(h3Index);
    let score = 0;
    for (const src of SUPPLY_SOURCES) score += anisotropicGaussian(lat, lng, src);
    for (const sink of DEMAND_SINKS)   score += anisotropicGaussian(lat, lng, sink);
    return score;
  });

  const minRaw = Math.min(...rawScores);
  const maxRaw = Math.max(...rawScores);
  const range = maxRaw - minRaw;

  // Second pass: normalize, add noise, and build output
  const data = cells.map((h3Index, i) => {
    const noise = (rand() - 0.5) * 0.06;
    const score = Math.max(0, Math.min(1, (rawScores[i] - minRaw) / range + noise));
    const surplusMwh = Math.round(score * 8000);
    return { h3Index, score, surplusMwh };
  });

  return data;
}

export function generateTexasCombinedData(resolution = 5) {
  const surplus = generateTexasHexData(resolution);
  const temp    = generateTexasTemperatureData(resolution);

  // Raw combined score: high surplus AND low temperature = best data center sites
  const raw = surplus.map((s, i) => s.score * (1 - temp[i].score));

  const minRaw = Math.min(...raw);
  const maxRaw = Math.max(...raw);
  const range  = maxRaw - minRaw;

  return surplus.map((s, i) => ({
    h3Index:    s.h3Index,
    score:      (raw[i] - minRaw) / range,
    surplusMwh: s.surplusMwh,
    tempF:      temp[i].tempF,
  }));
}
