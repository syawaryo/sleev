import { useState } from "react";
import type { FloorData, Sleeve, CheckResult } from "./types";
import { parseFloor, runChecks } from "./api";
import DrawingView from "./components/DrawingView";
import SleeveInfo from "./components/SleeveInfo";
import ResultsTable from "./components/ResultsTable";

function App() {
  const [floorData, setFloorData] = useState<FloorData | null>(null);
  const [results, setResults] = useState<CheckResult[]>([]);
  const [summary, setSummary] = useState<{ng: number; warning: number; ok: number} | null>(null);
  const [loading, setLoading] = useState(false);
  const [hoveredSleeve, setHoveredSleeve] = useState<Sleeve | null>(null);
  const [selectedSleeve, setSelectedSleeve] = useState<Sleeve | null>(null);
  const [filter, setFilter] = useState<"全て" | "NG" | "WARNING" | "OK">("全て");

  const handleRun = async () => {
    setLoading(true);
    try {
      const data = await parseFloor("2f");
      setFloorData(data);
      const checkRes = await runChecks("2f", "1f");
      setResults(checkRes.results);
      setSummary(checkRes.summary);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const displaySleeve = hoveredSleeve || selectedSleeve;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#0a0a1a", color: "#eee", fontFamily: "sans-serif" }}>
      {/* Header */}
      <div style={{ padding: "12px 24px", borderBottom: "1px solid #333", display: "flex", alignItems: "center", gap: 16 }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>スリーブチェッカー</h1>
        <button onClick={handleRun} disabled={loading}
                style={{ padding: "6px 20px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}>
          {loading ? "解析中..." : "チェック実行"}
        </button>
        {summary && (
          <div style={{ display: "flex", gap: 16, marginLeft: "auto" }}>
            <span style={{ color: "#ef4444" }}>NG: {summary.ng}</span>
            <span style={{ color: "#f59e0b" }}>WARNING: {summary.warning}</span>
            <span style={{ color: "#22c55e" }}>OK: {summary.ok}</span>
          </div>
        )}
      </div>

      {/* Main content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Drawing */}
        <div style={{ flex: 1, overflow: "hidden" }}>
          {floorData ? (
            <DrawingView
              floorData={floorData}
              results={results}
              onSleeveHover={setHoveredSleeve}
              onSleeveClick={setSelectedSleeve}
              selectedSleeveId={selectedSleeve?.id || null}
            />
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#666" }}>
              「チェック実行」を押してください
            </div>
          )}
        </div>

        {/* Right panel */}
        <div style={{ width: 320, borderLeft: "1px solid #333", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <SleeveInfo sleeve={displaySleeve} results={results} />
        </div>
      </div>

      {/* Bottom panel - Results table */}
      <div style={{ height: 300, borderTop: "1px solid #333", overflow: "auto", padding: "8px 16px" }}>
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
