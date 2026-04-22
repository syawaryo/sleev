import { useState, useRef, useEffect, useCallback } from "react";
import type { FloorData, Sleeve, CheckResult } from "./types";
import { getFloors, parseFloor, runChecks, uploadDxf, uploadDwg, uploadIfc } from "./api";
import DrawingView from "./components/DrawingView";
import SleeveInfo from "./components/SleeveInfo";
import ListView from "./components/ListView";
import DataExplorer from "./components/DataExplorer";
import * as pdfjs from "pdfjs-dist";

// Vite bundles the worker URL for us; pdf.js requires this or it falls back
// to main-thread rendering that often fails in production builds.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).href;

async function pdfFileToDataUrl(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const pdf = await pdfjs.getDocument({ data: buffer }).promise;
  const page = await pdf.getPage(1);
  const viewport = page.getViewport({ scale: 2 });
  const canvas = document.createElement("canvas");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  const ctx = canvas.getContext("2d")!;
  await page.render({ canvas, canvasContext: ctx, viewport } as any).promise;
  return canvas.toDataURL("image/png");
}

type ViewMode = "drawing" | "list" | "data";
type ColorMode = "severity" | "fl" | "discipline";

interface FloorEntry {
  id: string;
  label: string;
  source: "dxf" | "ifc" | "dwg";
  data: FloorData | null;
  results: CheckResult[];
}

function App() {
  const [floors, setFloors] = useState<FloorEntry[]>([]);
  const [activeFloorIdx, setActiveFloorIdx] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [colorMode, setColorMode] = useState<ColorMode>("severity");
  const [loading, setLoading] = useState(false);
  const [hoveredSleeve, setHoveredSleeve] = useState<Sleeve | null>(null);
  const [selectedSleeve, setSelectedSleeve] = useState<Sleeve | null>(null);
  const [filter, setFilter] = useState<"all" | "NG" | "WARNING" | "OK">("all");
  const [navigateTarget, setNavigateTarget] = useState<[number, number] | null>(null);
  const [highlightCoords, setHighlightCoords] = useState<[number, number][]>([]);
  const [openChecks, setOpenChecks] = useState<Set<number>>(new Set());
  const [layers, setLayers] = useState({
    grid: true, wall: true, outerWall: true, step: true, recess: true, column: true, sleeve: true, dim: false, lowerWall: false, slabLevel: false, raw: true,
  });
  const [sleeveFilters, setSleeveFilters] = useState({
    衛生: true, 空調: true, 電気: true, その他: true,
  });
  const toggleSleeveFilter = (key: keyof typeof sleeveFilters) =>
    setSleeveFilters((p) => ({ ...p, [key]: !p[key] }));
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dwgInputRef = useRef<HTMLInputElement>(null);
  const [ifcModalOpen, setIfcModalOpen] = useState(false);
  const [ifcSleeveFile, setIfcSleeveFile] = useState<File | null>(null);
  const [ifcStructureFile, setIfcStructureFile] = useState<File | null>(null);
  const [dwgConverting, setDwgConverting] = useState(false);
  const [dwgError, setDwgError] = useState<string | null>(null);
  const [pdfOverlayUrl, setPdfOverlayUrl] = useState<string | null>(null);
  const [pdfOverlayOpacity, setPdfOverlayOpacity] = useState(0.4);
  const pdfInputRef = useRef<HTMLInputElement>(null);

  const handleUploadPdf = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    try {
      const url = await pdfFileToDataUrl(files[0]);
      setPdfOverlayUrl(url);
    } catch (e) {
      console.error("PDF overlay failed:", e);
    }
    if (pdfInputRef.current) pdfInputRef.current.value = "";
  };

  const toggleLayer = (key: keyof typeof layers) =>
    setLayers((p) => ({ ...p, [key]: !p[key] }));

  // Stable callback so DrawingView's React.memo stays effective
  const handleNavigated = useCallback(() => setNavigateTarget(null), []);

  const activeFloor: FloorEntry = floors[activeFloorIdx] || { id: "", label: "", source: "dxf", data: null, results: [] };
  const floorData = activeFloor.data;
  const results = activeFloor.results;
  const displaySleeve = hoveredSleeve || selectedSleeve;

  // Find 1F data for wall interference overlay
  const floor1fData = floors.find((f) => f.id === "1f")?.data ?? null;

  // Sleeve counts per discipline (for filter badges)
  const sleeveCounts = (() => {
    const counts = { 衛生: 0, 空調: 0, 電気: 0, その他: 0 };
    if (!floorData) return counts;
    for (const s of floorData.sleeves) {
      const d = s.discipline as keyof typeof counts;
      if (d in counts) counts[d]++;
      else counts["その他"]++;
    }
    return counts;
  })();

  // Load existing floors on mount
  useEffect(() => {
    getFloors().then((serverFloors) => {
      if (serverFloors.length > 0) {
        setFloors(serverFloors.map((f) => ({
          id: f.id,
          label: f.name,
          source: (f.source === "ifc" ? "ifc" : "dxf") as "dxf" | "ifc",
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
          const entry: FloorEntry = { id: res.id, label: res.name, source: "dxf", data: null, results: [] };
          const exists = prev.findIndex((f) => f.id === res.id);
          if (exists >= 0) {
            const next = [...prev];
            next[exists] = entry;
            return next;
          }
          return [...prev, entry];
        });
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleUploadDwg = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setDwgError(null);
    setDwgConverting(true);
    setLoading(true);
    try {
      for (const file of Array.from(files)) {
        const res = await uploadDwg(file, "");
        setFloors((prev) => {
          const entry: FloorEntry = { id: res.id, label: res.name, source: "dwg", data: null, results: [] };
          const exists = prev.findIndex((f) => f.id === res.id);
          if (exists >= 0) {
            const next = [...prev];
            next[exists] = entry;
            return next;
          }
          return [...prev, entry];
        });
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? e?.message ?? "DWG変換に失敗しました";
      setDwgError(String(detail));
      console.error(e);
    }
    setDwgConverting(false);
    setLoading(false);
    if (dwgInputRef.current) dwgInputRef.current.value = "";
  };

  const handleIfcSubmit = async () => {
    if (!ifcSleeveFile) return;
    setLoading(true);
    try {
      const res = await uploadIfc(ifcSleeveFile, ifcStructureFile, "");
      setFloors((prev) => {
        const entry: FloorEntry = { id: res.id, label: res.name, source: "ifc", data: null, results: [] };
        const exists = prev.findIndex((f) => f.id === res.id);
        if (exists >= 0) {
          const next = [...prev];
          next[exists] = entry;
          return next;
        }
        return [...prev, entry];
      });
      setIfcModalOpen(false);
      setIfcSleeveFile(null);
      setIfcStructureFile(null);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
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

  const hasData = floors.some((f) => f.data !== null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#f8fafc", color: "#111827", fontFamily: "'Inter', 'Noto Sans JP', -apple-system, sans-serif" }}>
      {/* Row 1: Header */}
      <div className="no-print" style={{ background: "#fff", borderBottom: "1px solid #e5e7eb", padding: "10px 20px", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 16, fontWeight: 700, color: "#111827", letterSpacing: -0.3 }}>
          スリーブチェッカー
        </span>

        {/* View toggle */}
        <div style={{ display: "inline-flex", background: "#f3f4f6", borderRadius: 7, padding: 2, gap: 2, fontSize: 12, marginLeft: 12 }}>
          {([["list", "一覧"], ["drawing", "図面"], ["data", "データ"]] as const).map(([mode, label]) => (
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

        {hasData && (
          <button onClick={() => window.print()} className="no-print"
            style={{
              padding: "5px 12px", background: "#fff", color: "#374151",
              border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer",
              fontSize: 12, fontWeight: 500,
            }}>
            PDF出力
          </button>
        )}

      </div>

      {/* Hidden file inputs (always rendered) */}
      <input ref={fileInputRef} type="file" accept=".dxf" multiple style={{ display: "none" }}
        onChange={(e) => handleUpload(e.target.files)} />
      <input ref={dwgInputRef} type="file" accept=".dwg" multiple style={{ display: "none" }}
        onChange={(e) => handleUploadDwg(e.target.files)} />

      {/* Row 2: Floor tabs + controls */}
      <div className="no-print" style={{ background: "#fff", borderBottom: "1px solid #e5e7eb", padding: "6px 20px", display: "flex", alignItems: "center", gap: 10 }}>
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
                    display: "inline-flex", alignItems: "center", gap: 6,
                  }}>
                  {f.label}
                  <span style={{
                    fontSize: 9, fontWeight: 600, padding: "1px 5px", borderRadius: 3,
                    background: f.source === "ifc" ? "#dbeafe" : f.source === "dwg" ? "#fef3c7" : "#f3f4f6",
                    color: f.source === "ifc" ? "#1e40af" : f.source === "dwg" ? "#92400e" : "#6b7280",
                    letterSpacing: 0.3,
                  }}>{f.source.toUpperCase()}</span>
                </button>
                {!f.data && (
                  <button onClick={(e) => { e.stopPropagation(); handleRemoveFloor(i); }}
                    style={{ background: "none", border: "none", color: "#d1d5db", cursor: "pointer", fontSize: 10, padding: "0 4px", lineHeight: 1 }}
                    title="削除">x</button>
                )}
              </div>
            ))}
          </div>
        )}

        <button onClick={() => fileInputRef.current?.click()} disabled={loading}
          style={{ padding: "3px 12px", fontSize: 11, background: "#fff", border: "1px dashed #d1d5db", borderRadius: 6, color: "#9ca3af", cursor: "pointer" }}>
          + DXF追加
        </button>
        <button onClick={() => dwgInputRef.current?.click()} disabled={loading}
          style={{ padding: "3px 12px", fontSize: 11, background: "#fff", border: "1px dashed #d1d5db", borderRadius: 6, color: "#9ca3af", cursor: "pointer" }}>
          {dwgConverting ? "DWG変換中..." : "+ DWG追加"}
        </button>
        <button onClick={() => setIfcModalOpen(true)} disabled={loading}
          style={{ padding: "3px 12px", fontSize: 11, background: "#fff", border: "1px dashed #d1d5db", borderRadius: 6, color: "#9ca3af", cursor: "pointer" }}>
          + IFC追加
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
              ["outerWall", "外壁"],
              ["step", "スラブ段差"],
              ["recess", "床ヌスミ"],
              ["column", "柱・仕上"],
              ["dim", "寸法"],
              ["slabLevel", "スラブレベル"],
              ["raw", "その他(全要素)"],
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

            {/* Sleeve discipline sub-filters, shown when スリーブ layer is on */}
            {layers.sleeve && (
              <>
                <span style={{ color: "#d1d5db", margin: "0 2px" }}>›</span>
                {(["衛生", "空調", "電気", "その他"] as const).map((disc) => {
                  const on = sleeveFilters[disc];
                  const cnt = sleeveCounts[disc];
                  const color =
                    disc === "衛生" ? "#3b82f6" :
                    disc === "空調" ? "#f59e0b" :
                    disc === "電気" ? "#ef4444" : "#6b7280";
                  return (
                    <button key={disc}
                      onClick={() => toggleSleeveFilter(disc)}
                      disabled={cnt === 0}
                      style={{
                        padding: "2px 8px", borderRadius: 4, cursor: cnt === 0 ? "default" : "pointer", fontSize: 10,
                        border: `1px solid ${on && cnt > 0 ? color : "#e5e7eb"}`,
                        background: on && cnt > 0 ? `${color}15` : "#fff",
                        color: on && cnt > 0 ? color : "#d1d5db",
                        opacity: cnt === 0 ? 0.4 : 1,
                      }}>{disc} {cnt > 0 && <span style={{ opacity: 0.7 }}>({cnt})</span>}</button>
                  );
                })}
              </>
            )}

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

            <span style={{ color: "#d1d5db", margin: "0 4px" }}>|</span>
            <span style={{ color: "#9ca3af", fontSize: 10 }}>PDF重ね</span>
            <input
              ref={pdfInputRef}
              type="file"
              accept=".pdf"
              style={{ display: "none" }}
              onChange={(e) => handleUploadPdf(e.target.files)}
            />
            <button
              onClick={() => pdfInputRef.current?.click()}
              style={{
                padding: "2px 10px", borderRadius: 4, cursor: "pointer", fontSize: 10,
                border: "1px solid #d1d5db", background: pdfOverlayUrl ? "#eff6ff" : "#fff",
                color: pdfOverlayUrl ? "#1d4ed8" : "#374151",
              }}
            >{pdfOverlayUrl ? "PDF読込済" : "PDF選択"}</button>
            {pdfOverlayUrl && (
              <>
                <input
                  type="range" min={0} max={100} value={Math.round(pdfOverlayOpacity * 100)}
                  onChange={(e) => setPdfOverlayOpacity(Number(e.target.value) / 100)}
                  style={{ width: 80 }}
                />
                <span style={{ fontSize: 10, color: "#6b7280", minWidth: 28 }}>
                  {Math.round(pdfOverlayOpacity * 100)}%
                </span>
                <button
                  onClick={() => setPdfOverlayUrl(null)}
                  style={{
                    padding: "2px 6px", borderRadius: 4, cursor: "pointer", fontSize: 10,
                    border: "1px solid #e5e7eb", background: "#fff", color: "#6b7280",
                  }}
                >×</button>
              </>
            )}

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

      {/* DWG conversion error toast */}
      {dwgError && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 120, maxWidth: 420,
          background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8,
          padding: "12px 16px", boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
        }}>
          <div style={{ display: "flex", alignItems: "start", gap: 10 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#dc2626", marginBottom: 4 }}>
                DWG変換エラー
              </div>
              <div style={{ fontSize: 11, color: "#7f1d1d", lineHeight: 1.5 }}>{dwgError}</div>
            </div>
            <button onClick={() => setDwgError(null)}
              style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer", fontSize: 14, padding: 0, lineHeight: 1 }}>x</button>
          </div>
        </div>
      )}

      {/* IFC upload modal */}
      {ifcModalOpen && (
        <div
          onClick={() => !loading && setIfcModalOpen(false)}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)",
            zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ background: "#fff", borderRadius: 10, padding: 24, width: 460, boxShadow: "0 10px 40px rgba(0,0,0,0.15)" }}
          >
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>IFCファイルをアップロード</div>
            <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 18 }}>
              スリーブIFC（必須）と躯体IFC（任意）を指定してください。躯体IFCが無くても表示は可能ですが、一部チェック（下階壁干渉・段差等）は躯体IFC未提供扱いになります。
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 4 }}>スリーブIFC <span style={{ color: "#dc2626" }}>*</span></div>
              <input type="file" accept=".ifc"
                onChange={(e) => setIfcSleeveFile(e.target.files?.[0] ?? null)}
                style={{ fontSize: 12, width: "100%" }} />
              {ifcSleeveFile && (
                <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>{ifcSleeveFile.name}</div>
              )}
            </div>

            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 4 }}>躯体IFC（任意）</div>
              <input type="file" accept=".ifc"
                onChange={(e) => setIfcStructureFile(e.target.files?.[0] ?? null)}
                style={{ fontSize: 12, width: "100%" }} />
              {ifcStructureFile && (
                <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>{ifcStructureFile.name}</div>
              )}
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                onClick={() => { if (!loading) { setIfcModalOpen(false); setIfcSleeveFile(null); setIfcStructureFile(null); } }}
                disabled={loading}
                style={{ padding: "6px 16px", fontSize: 12, background: "#fff", border: "1px solid #d1d5db", borderRadius: 6, color: "#6b7280", cursor: "pointer" }}
              >キャンセル</button>
              <button
                onClick={handleIfcSubmit}
                disabled={!ifcSleeveFile || loading}
                style={{
                  padding: "6px 16px", fontSize: 12, border: "none", borderRadius: 6,
                  background: !ifcSleeveFile || loading ? "#d1d5db" : "#ff4b4b",
                  color: "#fff", cursor: !ifcSleeveFile || loading ? "default" : "pointer",
                  fontWeight: 500,
                }}
              >{loading ? "アップロード中..." : "アップロード"}</button>
            </div>
          </div>
        </div>
      )}

      {/* Main content */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
        {floors.length === 0 ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, color: "#9ca3af" }}>
            <div style={{ fontSize: 14 }}>DXFファイルをアップロードしてください</div>
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
                  sleeveFilters={sleeveFilters}
                  colorMode={colorMode}
                  navigateTarget={navigateTarget}
                  onNavigated={handleNavigated}
                  highlightCoords={highlightCoords}
                  pdfOverlayUrl={pdfOverlayUrl}
                  pdfOverlayOpacity={pdfOverlayOpacity}
                />
              ) : (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>
                  「チェック実行」を押してください
                </div>
              )}
            </div>
            {/* Right sidebar */}
            <div className="no-print" style={{ width: 300, borderLeft: "1px solid #e5e7eb", background: "#fff", overflow: "auto", flexShrink: 0 }}>
              {displaySleeve ? (
                <SleeveInfo sleeve={displaySleeve} results={results} />
              ) : (
                <div style={{ padding: 20, color: "#9ca3af", fontSize: 13, textAlign: "center", marginTop: 40 }}>
                  スリーブにカーソルを合わせると<br />詳細が表示されます
                </div>
              )}
            </div>
          </>
        ) : viewMode === "data" ? (
          <div style={{ flex: 1, overflow: "hidden" }}>
            {floorData ? (
              <DataExplorer
                floorData={floorData}
                onNavigate={(coords, sleeveId) => {
                  setViewMode("drawing");
                  setNavigateTarget(coords);
                  setHighlightCoords([]);
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
        ) : (
          <div style={{ flex: 1, overflow: "auto" }}>
            {floorData ? (
              <ListView
                floorData={floorData}
                results={results}
                filter={filter}
                openChecks={openChecks}
                onOpenChecksChange={setOpenChecks}
                onNavigate={(coords, sleeveId, relatedCoords) => {
                  setViewMode("drawing");
                  // Compute bounding center of all related coords so both base points are visible
                  const allPts = relatedCoords && relatedCoords.length > 1 ? relatedCoords : [coords];
                  const cx = allPts.reduce((s, p) => s + p[0], 0) / allPts.length;
                  const cy = allPts.reduce((s, p) => s + p[1], 0) / allPts.length;
                  setNavigateTarget([cx, cy]);
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

      {/* Print-only: results table appended on separate page(s) */}
      {hasData && (
        <div className="print-results" style={{ display: "none" }}>
          <style>{`@media print { .print-results { display: block !important; page-break-before: always; padding: 10mm; } }`}</style>
          <h2 style={{ fontSize: 14, marginBottom: 8 }}>
            {activeFloor.label} — チェック結果一覧
          </h2>
          <table>
            <thead>
              <tr>
                <th style={{ width: "8%" }}>No.</th>
                <th style={{ width: "10%" }}>重要度</th>
                <th style={{ width: "20%" }}>チェック項目</th>
                <th style={{ width: "12%" }}>P-N</th>
                <th>メッセージ</th>
              </tr>
            </thead>
            <tbody>
              {results
                .filter((r) => r.severity !== "OK")
                .map((r, i) => {
                  const sleeve = r.sleeve_id
                    ? floorData?.sleeves.find((s) => s.id === r.sleeve_id)
                    : null;
                  return (
                    <tr key={i}>
                      <td>{r.check_id}</td>
                      <td style={{
                        color: r.severity === "NG" ? "#dc2626" : "#d97706",
                        fontWeight: 600,
                      }}>{r.severity}</td>
                      <td>{r.check_name}</td>
                      <td>{sleeve?.pn_number || r.sleeve_id || "-"}</td>
                      <td>{r.message}</td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
          <div style={{ marginTop: 10, fontSize: 10, color: "#6b7280" }}>
            出力日時: {new Date().toLocaleString("ja-JP")}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
