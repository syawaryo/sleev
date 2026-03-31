import { useState, useMemo, useRef, useEffect } from "react";
import type { FloorData, Sleeve, CheckResult } from "./types";
import { getFloors, parseFloor, runChecks, uploadDxf } from "./api";
import DrawingView from "./components/DrawingView";
import SleeveInfo from "./components/SleeveInfo";
import ListView from "./components/ListView";

type ViewMode = "drawing" | "list";
type ColorMode = "severity" | "fl" | "discipline";

interface FloorEntry {
  id: string;
  label: string;
  data: FloorData | null;
  results: CheckResult[];
}

function App() {
  const [floors, setFloors] = useState<FloorEntry[]>([]);
  const [activeFloorIdx, setActiveFloorIdx] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("drawing");
  const [colorMode, setColorMode] = useState<ColorMode>("severity");
  const [loading, setLoading] = useState(false);
  const [hoveredSleeve, setHoveredSleeve] = useState<Sleeve | null>(null);
  const [selectedSleeve, setSelectedSleeve] = useState<Sleeve | null>(null);
  const [filter, setFilter] = useState<"all" | "NG" | "WARNING" | "OK">("all");
  const [navigateTarget, setNavigateTarget] = useState<[number, number] | null>(null);
  const [highlightCoords, setHighlightCoords] = useState<[number, number][]>([]);
  const [layers, setLayers] = useState({
    grid: true, wall: true, step: true, column: true, sleeve: true, dim: false, lowerWall: false, slabLevel: false,
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toggleLayer = (key: keyof typeof layers) =>
    setLayers((p) => ({ ...p, [key]: !p[key] }));

  const activeFloor = floors[activeFloorIdx] || { id: "", label: "", data: null, results: [] };
  const floorData = activeFloor.data;
  const results = activeFloor.results;
  const displaySleeve = hoveredSleeve || selectedSleeve;

  // Find 1F data for wall interference overlay
  const floor1fData = floors.find((f) => f.id === "1f")?.data ?? null;

  // Load existing floors on mount
  useEffect(() => {
    getFloors().then((serverFloors) => {
      if (serverFloors.length > 0) {
        setFloors(serverFloors.map((f) => ({
          id: f.id,
          label: f.name,
          data: null,
          results: [],
        })));
      }
    }).catch(() => {});
  }, []);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setLoading(true);
    try {
      for (const file of Array.from(files)) {
        const res = await uploadDxf(file, "");
        setFloors((prev) => {
          const exists = prev.findIndex((f) => f.id === res.id);
          if (exists >= 0) {
            const next = [...prev];
            next[exists] = { id: res.id, label: res.name, data: null, results: [] };
            return next;
          }
          return [...prev, { id: res.id, label: res.name, data: null, results: [] }];
        });
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleRun = async () => {
    if (floors.length === 0) return;
    setLoading(true);
    try {
      // Parse all floors
      const parsed = await Promise.all(floors.map((f) => parseFloor(f.id)));

      // Find floor pairs: for each floor, find the one below it for wall check
      // Simple heuristic: if there's a "1f" floor, use it as lower for "2f"
      const floor1fId = floors.find((f) => f.id === "1f")?.id ?? null;

      const checked = await Promise.all(
        floors.map((f) => {
          const lower = f.id !== "1f" && floor1fId ? floor1fId : undefined;
          return runChecks(f.id, lower);
        })
      );

      setFloors(
        floors.map((f, i) => ({
          ...f,
          data: parsed[i],
          results: checked[i].results,
        }))
      );
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleRemoveFloor = (idx: number) => {
    setFloors((prev) => prev.filter((_, i) => i !== idx));
    if (activeFloorIdx >= floors.length - 1) {
      setActiveFloorIdx(Math.max(0, floors.length - 2));
    }
  };

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

  const hasData = floors.some((f) => f.data !== null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#f8fafc", color: "#111827", fontFamily: "'Inter', 'Noto Sans JP', -apple-system, sans-serif" }}>
      {/* Row 1: Header */}
      <div style={{ background: "#fff", borderBottom: "1px solid #e5e7eb", padding: "10px 20px", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 16, fontWeight: 700, color: "#111827", letterSpacing: -0.3 }}>
          スリーブチェッカー
        </span>

        {/* View toggle */}
        <div style={{ display: "inline-flex", background: "#f3f4f6", borderRadius: 7, padding: 2, gap: 2, fontSize: 12, marginLeft: 12 }}>
          {([["drawing", "図面"], ["list", "一覧"]] as const).map(([mode, label]) => (
            <button key={mode} onClick={() => setViewMode(mode)}
              style={{
                padding: "4px 14px", border: "none", borderRadius: 5, cursor: "pointer", fontSize: 12, fontWeight: viewMode === mode ? 500 : 400,
                background: viewMode === mode ? "#111827" : "transparent",
                color: viewMode === mode ? "#fff" : "#9ca3af",
              }}>{label}</button>
          ))}
        </div>

        {floors.length > 0 && (
          <button onClick={handleRun} disabled={loading}
            style={{
              padding: "5px 16px", background: loading ? "#d1d5db" : "#ff4b4b",
              color: "#fff", border: "none", borderRadius: 6, cursor: loading ? "default" : "pointer",
              fontSize: 12, fontWeight: 500, marginLeft: 8,
            }}>
            {loading ? "解析中..." : hasData ? "再チェック" : "チェック実行"}
          </button>
        )}

        {/* Summary */}
        {sleeveSummary && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 6, fontSize: 11, alignItems: "center" }}>
            <span style={{ color: "#9ca3af" }}>{sleeveSummary.total} スリーブ</span>
            <span style={{ background: "#fef2f2", color: "#dc2626", padding: "1px 8px", borderRadius: 4, fontWeight: 600 }}>{sleeveSummary.ng} NG</span>
            <span style={{ background: "#fffbeb", color: "#d97706", padding: "1px 8px", borderRadius: 4, fontWeight: 600 }}>{sleeveSummary.warning} WARN</span>
            <span style={{ background: "#f0fdf4", color: "#16a34a", padding: "1px 8px", borderRadius: 4, fontWeight: 600 }}>{sleeveSummary.ok} OK</span>
          </div>
        )}
      </div>

      {/* Row 2: Floor tabs + controls */}
      <div style={{ background: "#fff", borderBottom: "1px solid #e5e7eb", padding: "6px 20px", display: "flex", alignItems: "center", gap: 10 }}>
        {/* Floor segment */}
        {floors.length > 0 && (
          <div style={{ display: "inline-flex", background: "#f3f4f6", borderRadius: 7, padding: 2, gap: 2, fontSize: 12 }}>
            {floors.map((f, i) => (
              <div key={f.id} style={{ display: "inline-flex", alignItems: "center" }}>
                <button
                  onClick={() => { setActiveFloorIdx(i); setSelectedSleeve(null); setHoveredSleeve(null); }}
                  style={{
                    padding: "4px 16px", border: "none", borderRadius: 5, cursor: "pointer", fontSize: 12,
                    fontWeight: activeFloorIdx === i ? 500 : 400,
                    background: activeFloorIdx === i ? "#fff" : "transparent",
                    color: activeFloorIdx === i ? "#111827" : "#9ca3af",
                    boxShadow: activeFloorIdx === i ? "0 1px 2px rgba(0,0,0,0.06)" : "none",
                  }}>{f.label}</button>
                {!f.data && (
                  <button onClick={(e) => { e.stopPropagation(); handleRemoveFloor(i); }}
                    style={{ background: "none", border: "none", color: "#d1d5db", cursor: "pointer", fontSize: 10, padding: "0 4px", lineHeight: 1 }}
                    title="削除">x</button>
                )}
              </div>
            ))}
          </div>
        )}

        <input ref={fileInputRef} type="file" accept=".dxf" multiple style={{ display: "none" }}
          onChange={(e) => handleUpload(e.target.files)} />
        <button onClick={() => fileInputRef.current?.click()} disabled={loading}
          style={{ padding: "3px 12px", fontSize: 11, background: "#fff", border: "1px dashed #d1d5db", borderRadius: 6, color: "#9ca3af", cursor: "pointer" }}>
          + DXF追加
        </button>

        {/* List mode filters */}
        {viewMode === "list" && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 4, fontSize: 11 }}>
            {([["all", "全て"], ["NG", "NG"], ["WARNING", "WARN"], ["OK", "OK"]] as const).map(([val, label]) => {
              const isActive = filter === val;
              const colors: Record<string, { border: string; color: string; bg: string }> = {
                NG: { border: "#fecaca", color: "#dc2626", bg: "#fef2f2" },
                WARNING: { border: "#fde68a", color: "#d97706", bg: "#fffbeb" },
                OK: { border: "#bbf7d0", color: "#16a34a", bg: "#f0fdf4" },
              };
              const c = colors[val];
              return (
                <button key={val} onClick={() => setFilter(val)}
                  style={{
                    padding: "3px 10px", borderRadius: 4, cursor: "pointer", fontSize: 11, border: "1px solid",
                    borderColor: isActive ? (c?.border || "#d1d5db") : "#e5e7eb",
                    background: isActive ? (c?.bg || "#f3f4f6") : "#fff",
                    color: c?.color || "#111827",
                    fontWeight: isActive ? 500 : 400,
                  }}>{label}</button>
              );
            })}
          </div>
        )}

        {/* Drawing mode layer controls */}
        {viewMode === "drawing" && floorData && (
          <>
            <span style={{ color: "#d1d5db", margin: "0 4px" }}>|</span>
            <span style={{ color: "#9ca3af", fontSize: 10 }}>レイヤー</span>
            {([
              ["grid", "通り芯"],
              ["wall", "壁"],
              ["step", "段差線"],
              ["column", "柱・仕上"],
              ["dim", "寸法"],
              ["slabLevel", "スラブレベル"],
              ["sleeve", "スリーブ"],
              ...(activeFloor.id === "2f" ? [["lowerWall", "1F壁"]] : []),
            ] as string[][]).map(([key, label]) => {
              const on = layers[key as keyof typeof layers];
              return (
                <button key={key}
                  onClick={() => toggleLayer(key as keyof typeof layers)}
                  style={{
                    padding: "2px 10px", borderRadius: 4, cursor: "pointer", fontSize: 10,
                    border: `1px solid ${on ? "#9ca3af" : "#e5e7eb"}`,
                    background: on ? "#f3f4f6" : "#fff",
                    color: on ? "#374151" : "#d1d5db",
                  }}>{label}</button>
              );
            })}

            <span style={{ color: "#d1d5db", margin: "0 4px" }}>|</span>
            <span style={{ color: "#9ca3af", fontSize: 10 }}>色分け</span>
            <div style={{ display: "inline-flex", background: "#f3f4f6", borderRadius: 5, padding: 2, gap: 1 }}>
              {([["severity", "判定"], ["fl", "FL高さ"], ["discipline", "設備"]] as const).map(([mode, label]) => (
                <button key={mode} onClick={() => setColorMode(mode)}
                  style={{
                    padding: "2px 10px", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 10,
                    fontWeight: colorMode === mode ? 500 : 400,
                    background: colorMode === mode ? "#fff" : "transparent",
                    color: colorMode === mode ? "#111827" : "#9ca3af",
                    boxShadow: colorMode === mode ? "0 1px 2px rgba(0,0,0,0.05)" : "none",
                  }}>{label}</button>
              ))}
            </div>

            {/* Color legend */}
            {colorMode === "severity" && (
              <div style={{ display: "flex", gap: 8, fontSize: 10, alignItems: "center", marginLeft: 4 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 3 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#dc2626", display: "inline-block" }} />NG</span>
                <span style={{ display: "flex", alignItems: "center", gap: 3 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#d97706", display: "inline-block" }} />WARN</span>
                <span style={{ display: "flex", alignItems: "center", gap: 3 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#16a34a", display: "inline-block" }} />OK</span>
              </div>
            )}
            {colorMode === "discipline" && (
              <div style={{ display: "flex", gap: 8, fontSize: 10, alignItems: "center", marginLeft: 4 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 3 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#3b82f6", display: "inline-block" }} />衛生</span>
                <span style={{ display: "flex", alignItems: "center", gap: 3 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#f59e0b", display: "inline-block" }} />空調</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Main content */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
        {floors.length === 0 ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, color: "#9ca3af" }}>
            <div style={{ fontSize: 14 }}>DXFファイルをアップロードしてください</div>
            <input ref={fileInputRef} type="file" accept=".dxf" multiple style={{ display: "none" }}
              onChange={(e) => handleUpload(e.target.files)} />
            <button onClick={() => fileInputRef.current?.click()}
              style={{
                padding: "10px 24px", fontSize: 13, background: "#fff", border: "2px dashed #d1d5db",
                borderRadius: 8, color: "#6b7280", cursor: "pointer",
              }}>
              + DXFファイルを選択
            </button>
          </div>
        ) : viewMode === "drawing" ? (
          <>
            {/* Drawing area */}
            <div style={{ flex: 1, overflow: "hidden" }}>
              {floorData ? (
                <DrawingView
                  floorData={floorData}
                  lowerFloorData={activeFloor.id === "2f" && layers.lowerWall ? floor1fData : null}
                  results={results}
                  onSleeveHover={setHoveredSleeve}
                  onSleeveClick={setSelectedSleeve}
                  selectedSleeveId={selectedSleeve?.id || null}
                  layers={layers}
                  colorMode={colorMode}
                  navigateTarget={navigateTarget}
                  onNavigated={() => setNavigateTarget(null)}
                  highlightCoords={highlightCoords}
                />
              ) : (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>
                  「チェック実行」を押してください
                </div>
              )}
            </div>
            {/* Right sidebar */}
            <div style={{ width: 300, borderLeft: "1px solid #e5e7eb", background: "#fff", overflow: "auto", flexShrink: 0 }}>
              {displaySleeve ? (
                <SleeveInfo sleeve={displaySleeve} results={results} />
              ) : (
                <div style={{ padding: 20, color: "#9ca3af", fontSize: 13, textAlign: "center", marginTop: 40 }}>
                  スリーブにカーソルを合わせると<br />詳細が表示されます
                </div>
              )}
            </div>
          </>
        ) : (
          <div style={{ flex: 1, overflow: "auto" }}>
            {floorData ? (
              <ListView
                floorData={floorData}
                results={results}
                filter={filter}
                onNavigate={(coords, sleeveId, relatedCoords) => {
                  setViewMode("drawing");
                  setNavigateTarget(coords);
                  setHighlightCoords(relatedCoords || []);
                  if (sleeveId) {
                    const sleeve = floorData?.sleeves.find(s => s.id === sleeveId);
                    if (sleeve) setSelectedSleeve(sleeve);
                  } else {
                    setSelectedSleeve(null);
                  }
                }}
              />
            ) : (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>
                「チェック実行」を押してください
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
