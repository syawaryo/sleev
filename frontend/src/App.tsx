import { useState, useMemo } from "react";
import type { FloorData, Sleeve, CheckResult } from "./types";
import { parseFloor, runChecks } from "./api";
import DrawingView from "./components/DrawingView";
import SleeveInfo from "./components/SleeveInfo";
import ResultsTable from "./components/ResultsTable";

type FloorTab = "2f" | "1f";
type ColorMode = "severity" | "fl";

function App() {
  const [floor2f, setFloor2f] = useState<FloorData | null>(null);
  const [floor1f, setFloor1f] = useState<FloorData | null>(null);
  const [results2f, setResults2f] = useState<CheckResult[]>([]);
  const [results1f, setResults1f] = useState<CheckResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [hoveredSleeve, setHoveredSleeve] = useState<Sleeve | null>(null);
  const [selectedSleeve, setSelectedSleeve] = useState<Sleeve | null>(null);
  const [filter, setFilter] = useState<"\u5168\u3066" | "NG" | "WARNING" | "OK">("\u5168\u3066");
  const [activeFloor, setActiveFloor] = useState<FloorTab>("2f");
  const [colorMode, setColorMode] = useState<ColorMode>("severity");

  // Layer visibility
  const [layers, setLayers] = useState({
    grid: true,
    wall: true,
    step: true,
    sleeve: true,
    lowerWall: false,
  });
  const toggleLayer = (key: keyof typeof layers) =>
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleRun = async () => {
    setLoading(true);
    try {
      const [data2f, data1f] = await Promise.all([parseFloor("2f"), parseFloor("1f")]);
      setFloor2f(data2f);
      setFloor1f(data1f);
      const [check2f, check1f] = await Promise.all([
        runChecks("2f", "1f"),
        runChecks("1f"),
      ]);
      setResults2f(check2f.results);
      setResults1f(check1f.results);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const floorData = activeFloor === "2f" ? floor2f : floor1f;
  const results = activeFloor === "2f" ? results2f : results1f;
  const displaySleeve = hoveredSleeve || selectedSleeve;

  // Sleeve-level summary
  const sleeveSummary = useMemo(() => {
    if (!floorData) return null;
    const worst = new Map<string, string>();
    for (const r of results) {
      if (!r.sleeve_id) continue;
      const cur = worst.get(r.sleeve_id);
      if (!cur || r.severity === "NG" || (r.severity === "WARNING" && cur === "OK")) {
        worst.set(r.sleeve_id, r.severity);
      }
    }
    let ng = 0, warn = 0, ok = 0;
    for (const v of worst.values()) {
      if (v === "NG") ng++;
      else if (v === "WARNING") warn++;
      else ok++;
    }
    return { total: floorData.sleeves.length, ng, warning: warn, ok };
  }, [floorData, results]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#111827", color: "#e5e7eb", fontFamily: "'Segoe UI', 'Noto Sans JP', sans-serif" }}>
      {/* Header */}
      <div style={{ padding: "10px 20px", background: "#1f2937", borderBottom: "1px solid #374151", display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: "#f9fafb" }}>
          スリーブチェッカー
        </h1>

        {/* Floor tabs */}
        <div style={{ display: "flex", gap: 2, marginLeft: 16, background: "#374151", borderRadius: 6, padding: 2 }}>
          {([["2f", "2階"], ["1f", "1階"]] as const).map(([id, label]) => (
            <button key={id} onClick={() => { setActiveFloor(id); setSelectedSleeve(null); setHoveredSleeve(null); }}
              style={{
                padding: "4px 16px", border: "none", borderRadius: 4, fontSize: 13, cursor: "pointer",
                background: activeFloor === id ? "#3b82f6" : "transparent",
                color: activeFloor === id ? "#fff" : "#9ca3af",
              }}>
              {label}
            </button>
          ))}
        </div>

        <button onClick={handleRun} disabled={loading}
          style={{
            padding: "6px 20px", background: loading ? "#4b5563" : "#3b82f6",
            color: "#fff", border: "none", borderRadius: 6, cursor: loading ? "default" : "pointer",
            fontSize: 13, fontWeight: 500,
          }}>
          {loading ? "解析中..." : "チェック実行"}
        </button>

        {/* Sleeve-level summary */}
        {sleeveSummary && (
          <div style={{ display: "flex", gap: 16, marginLeft: "auto", fontSize: 13 }}>
            <span style={{ color: "#9ca3af" }}>スリーブ: {sleeveSummary.total}</span>
            <span style={{ color: "#f87171", fontWeight: 600 }}>NG: {sleeveSummary.ng}</span>
            <span style={{ color: "#fbbf24", fontWeight: 600 }}>WARN: {sleeveSummary.warning}</span>
            <span style={{ color: "#34d399", fontWeight: 600 }}>OK: {sleeveSummary.ok}</span>
          </div>
        )}
      </div>

      {/* Controls bar */}
      {floorData && (
        <div style={{ padding: "6px 20px", background: "#1a2332", borderBottom: "1px solid #2d3748", display: "flex", gap: 12, alignItems: "center", fontSize: 12 }}>
          <span style={{ color: "#6b7280" }}>レイヤー:</span>
          {([
            ["grid", "通り芯", "#6b7280"],
            ["wall", "壁", "#8b9dc3"],
            ["step", "段差線", "#d97706"],
            ["sleeve", "スリーブ", "#60a5fa"],
            ...(activeFloor === "2f" ? [["lowerWall", "1F壁(干渉)", "#a78bfa"] as const] : []),
          ] as const).map(([key, label, color]) => (
            <button key={key}
              onClick={() => toggleLayer(key as keyof typeof layers)}
              style={{
                padding: "2px 10px", borderRadius: 3, fontSize: 11, cursor: "pointer",
                border: `1px solid ${layers[key as keyof typeof layers] ? color : "#4b5563"}`,
                background: layers[key as keyof typeof layers] ? color + "20" : "transparent",
                color: layers[key as keyof typeof layers] ? color : "#6b7280",
              }}>
              {label}
            </button>
          ))}
          <span style={{ color: "#4b5563" }}>|</span>
          <span style={{ color: "#6b7280" }}>色分け:</span>
          {([["severity", "判定結果"], ["fl", "FL高さ"]] as const).map(([mode, label]) => (
            <button key={mode} onClick={() => setColorMode(mode)}
              style={{
                padding: "2px 10px", borderRadius: 3, fontSize: 11, cursor: "pointer",
                border: `1px solid ${colorMode === mode ? "#60a5fa" : "#4b5563"}`,
                background: colorMode === mode ? "#60a5fa20" : "transparent",
                color: colorMode === mode ? "#60a5fa" : "#6b7280",
              }}>
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Main content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Drawing */}
        <div style={{ flex: 1, overflow: "hidden" }}>
          {floorData ? (
            <DrawingView
              floorData={floorData}
              lowerFloorData={activeFloor === "2f" && layers.lowerWall ? floor1f : null}
              results={results}
              onSleeveHover={setHoveredSleeve}
              onSleeveClick={setSelectedSleeve}
              selectedSleeveId={selectedSleeve?.id || null}
              layers={layers}
              colorMode={colorMode}
            />
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#4b5563" }}>
              「チェック実行」を押してください
            </div>
          )}
        </div>

        {/* Right panel */}
        <div style={{ width: 340, borderLeft: "1px solid #2d3748", background: "#1a2332", display: "flex", flexDirection: "column", overflow: "auto" }}>
          <SleeveInfo sleeve={displaySleeve} results={results} />
        </div>
      </div>

      {/* Bottom panel */}
      <div style={{ height: 280, borderTop: "1px solid #2d3748", background: "#1a2332", overflow: "auto", padding: "8px 16px" }}>
        <ResultsTable
          results={results}
          selectedSleeveId={selectedSleeve?.id || null}
          filter={filter}
          onFilterChange={setFilter}
        />
      </div>
    </div>
  );
}

export default App;
