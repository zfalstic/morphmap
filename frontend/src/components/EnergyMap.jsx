import { useMemo, useState } from "react";
import Map from "react-map-gl/maplibre";
import DeckGL from "@deck.gl/react";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { generateTexasHexData, generateTexasTemperatureData, generateTexasCombinedData } from "../data/generateTexasData";
import "maplibre-gl/dist/maplibre-gl.css";

const CARTO_DARK_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const INITIAL_VIEW = {
  longitude: -99.5,
  latitude: 31.0,
  zoom: 5.5,
  pitch: 0,
  bearing: 0,
};

function surplusColor(score) {
  const r = Math.round(score * 20);
  const g = Math.round(180 + score * 75);
  const b = Math.round(220 - score * 80);
  const a = Math.round(30 + score * 200);
  return [r, g, b, a];
}

function temperatureColor(score) {
  // Low: faint amber → High: vivid red-orange
  const r = 255;
  const g = Math.round(180 - score * 150);  // 180 → 30
  const b = Math.round(20  - score * 20);   // 20  → 0
  const a = Math.round(25  + score * 210);  // 25  → 235
  return [r, g, b, a];
}

function combinedColor(score) {
  // Low: barely visible deep purple → High: vivid electric violet
  const r = Math.round(80  + score * 130);  // 80  → 210
  const g = Math.round(0   + score * 20);   // near-zero throughout
  const b = Math.round(180 + score * 75);   // 180 → 255
  const a = Math.round(25  + score * 215);  // 25  → 240
  return [r, g, b, a];
}

export default function EnergyMap({ activeLayer }) {
  const [tooltip, setTooltip] = useState(null);

  const surplusData     = useMemo(() => generateTexasHexData(5), []);
  const temperatureData = useMemo(() => generateTexasTemperatureData(5), []);
  const combinedData    = useMemo(() => generateTexasCombinedData(5), []);

  const layerMap = {
    surplus:     { data: surplusData,     getColor: (d) => surplusColor(d.score),     lineColor: [0, 255, 200, 15] },
    temperature: { data: temperatureData, getColor: (d) => temperatureColor(d.score), lineColor: [255, 120, 0, 15] },
    combined:    { data: combinedData,    getColor: (d) => combinedColor(d.score),     lineColor: [140, 0, 255, 15] },
  };

  const { data, getColor, lineColor } = layerMap[activeLayer];

  const layer = new H3HexagonLayer({
    id: `layer-${activeLayer}`,
    data,
    getHexagon: (d) => d.h3Index,
    getFillColor: getColor,
    getElevation: 0,
    elevationScale: 0,
    extruded: false,
    filled: true,
    stroked: true,
    getLineColor: lineColor,
    lineWidthMinPixels: 0.3,
    pickable: true,
    onHover: (info) => {
      if (info.object) {
        setTooltip({ x: info.x, y: info.y, data: info.object });
      } else {
        setTooltip(null);
      }
    },
  });

  const accents = {
    surplus:     { color: "#00ffc8", dim: "rgba(0,255,200,0.35)",   muted: "#5a8a78" },
    temperature: { color: "#ff8c00", dim: "rgba(255,140,0,0.35)",   muted: "#8a6030" },
    combined:    { color: "#c060ff", dim: "rgba(160,0,255,0.35)",   muted: "#7040a0" },
  };
  const { color: accentColor, dim: accentDim, muted: accentMuted } = accents[activeLayer];

  return (
    <div style={{ width: "100vw", height: "100vh", position: "relative", background: "#050a0e" }}>
      <DeckGL initialViewState={INITIAL_VIEW} controller={true} layers={[layer]}>
        <Map mapStyle={CARTO_DARK_STYLE} />
      </DeckGL>

      {tooltip && (
        <div
          style={{
            position: "absolute",
            left: tooltip.x + 12,
            top: tooltip.y - 44,
            background: "rgba(5,15,20,0.92)",
            border: `1px solid ${accentDim}`,
            borderRadius: 4,
            padding: "6px 10px",
            color: accentColor,
            fontFamily: "'JetBrains Mono', 'Courier New', monospace",
            fontSize: 12,
            pointerEvents: "none",
            whiteSpace: "nowrap",
          }}
        >
          {activeLayer === "surplus" && (
            <>
              <div style={{ color: accentColor, fontSize: 10, marginBottom: 2 }}>NET SURPLUS</div>
              <div>{tooltip.data.surplusMwh.toLocaleString()} MWh</div>
              <div style={{ color: accentMuted, fontSize: 10, marginTop: 2 }}>
                score: {(tooltip.data.score * 100).toFixed(1)}
              </div>
            </>
          )}
          {activeLayer === "temperature" && (
            <>
              <div style={{ color: accentColor, fontSize: 10, marginBottom: 2 }}>AVG TEMPERATURE</div>
              <div>{tooltip.data.tempF}°F</div>
              <div style={{ color: accentMuted, fontSize: 10, marginTop: 2 }}>
                score: {(tooltip.data.score * 100).toFixed(1)}
              </div>
            </>
          )}
          {activeLayer === "combined" && (
            <>
              <div style={{ color: accentColor, fontSize: 10, marginBottom: 2 }}>SITE SCORE</div>
              <div style={{ fontSize: 14, fontWeight: "bold" }}>{(tooltip.data.score * 100).toFixed(0)}<span style={{ fontSize: 10, marginLeft: 2 }}>/100</span></div>
              <div style={{ color: accentMuted, fontSize: 10, marginTop: 3 }}>
                {tooltip.data.surplusMwh.toLocaleString()} MWh · {tooltip.data.tempF}°F
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
