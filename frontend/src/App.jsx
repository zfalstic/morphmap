import { useState } from "react";
import EnergyMap from "./components/EnergyMap";
import "./App.css";

const LAYERS = {
  surplus: {
    label: "ENERGY SURPLUS",
    sub: "Net MWh · Supply minus Demand",
    legendMin: "0 MWh",
    legendMax: "8,000 MWh",
    legendNote: "Opacity = surplus intensity",
    gradientCss: "linear-gradient(to right, rgba(0,200,180,0.1), rgba(0,255,200,1))",
    accent: "#00ffc8",
    accentBorder: "rgba(0,255,200,0.35)",
  },
  temperature: {
    label: "AVG TEMPERATURE",
    sub: "Degrees Fahrenheit · Synthetic",
    legendMin: "65°F",
    legendMax: "115°F",
    legendNote: "Opacity = heat intensity",
    gradientCss: "linear-gradient(to right, rgba(255,180,20,0.15), rgba(255,40,0,1))",
    accent: "#ff8c00",
    accentBorder: "rgba(255,140,0,0.35)",
  },
  combined: {
    label: "SITE SCORE",
    sub: "High Surplus × Low Temperature",
    legendMin: "Poor",
    legendMax: "Optimal",
    legendNote: "Best data center sites",
    gradientCss: "linear-gradient(to right, rgba(100,0,200,0.1), rgba(180,60,255,1))",
    accent: "#c060ff",
    accentBorder: "rgba(160,0,255,0.35)",
  },
};

export default function App() {
  const [activeLayer, setActiveLayer] = useState("surplus");
  const cfg = LAYERS[activeLayer];

  return (
    <div className="app-shell">
      {/* Title bar */}
      <header className="title-bar">
        <div className="title-bar-left">
          <span className="title-bar-label">GRID SURPLUS INTELLIGENCE</span>
          <span className="title-bar-sub">Texas · ERCOT · H3 Resolution 5</span>
        </div>
        <div className="title-bar-right">
          <span className="status-dot" style={{ background: cfg.accent, boxShadow: `0 0 6px ${cfg.accent}` }} />
          <span className="status-text">LIVE PREVIEW — SYNTHETIC DATA</span>
        </div>
      </header>

      {/* Layer selector */}
      <div className="layer-selector">
        {Object.entries(LAYERS).map(([key, meta]) => (
          <button
            key={key}
            className={`layer-btn ${activeLayer === key ? "active" : ""}`}
            style={activeLayer === key ? { "--accent": meta.accent, "--accent-border": meta.accentBorder } : {}}
            onClick={() => setActiveLayer(key)}
          >
            {meta.label}
          </button>
        ))}
      </div>

      {/* Full-screen map */}
      <main className="map-container">
        <EnergyMap activeLayer={activeLayer} />
      </main>

      {/* Dynamic legend */}
      <div className="legend" style={{ "--accent": cfg.accent, "--accent-border": cfg.accentBorder }}>
        <div className="legend-title">{cfg.label}</div>
        <div className="legend-sub">{cfg.sub}</div>
        <div className="legend-gradient" style={{ background: cfg.gradientCss }} />
        <div className="legend-labels">
          <span>{cfg.legendMin}</span>
          <span>{cfg.legendMax}</span>
        </div>
        <div className="legend-note">{cfg.legendNote}</div>
      </div>
    </div>
  );
}
