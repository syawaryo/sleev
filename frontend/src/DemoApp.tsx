import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import type { CheckResult, FloorData, Sleeve } from "./types";
import { listFloorData, loadDrawing, loadManifest } from "./demoData";
import type { DemoManifest } from "./demoData";
import ListView from "./components/ListView";
import SleeveInfo from "./components/SleeveInfo";
import FocusedCheckResult from "./components/FocusedCheckResult";

const DrawingView = lazy(() => import("./components/DrawingView"));
const DemoDataView = lazy(() => import("./components/DemoDataView"));
const tabs = [["checklist", "チェック観点"], ["drawing", "図面"], ["list", "チェック結果"], ["data", "図面データ"]] as const;
type View = typeof tabs[number][0];
const initialLayers = {
  grid: true, kutaiheki: true, kanshikiheki: true, firewall: true, column: true,
  beam: false, slabOutline: true, slabLabel: false, slabFL: false, step: true,
  recess: true, flLabel: false, dim: false, pn: true, room: false,
  waterGradient: false, equipSanitary: false, equipHvac: false, equipElectric: false,
  sleeve: true, lowerWall: false, slabLevel: false, flZone: false, raw: false,
};
const sleeveFilters = { 衛生: true, 空調: true, 電気: true, その他: true };
const noop = () => {};
const buttonStyle = { padding: "5px 14px", background: "#fff", color: "#374151", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 500 };

export default function DemoApp() {
  const [manifest, setManifest] = useState<DemoManifest | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [activeId, setActiveId] = useState("");
  const [view, setView] = useState<View>("list");
  const [drawings, setDrawings] = useState<Record<string, FloorData>>({});
  const [drawingError, setDrawingError] = useState("");
  const [drawingRetry, setDrawingRetry] = useState(0);
  const [selected, setSelected] = useState<Sleeve | null>(null);
  const [selectedResult, setSelectedResult] = useState<CheckResult | null>(null);
  const [target, setTarget] = useState<[number, number] | null>(null);
  const [highlights, setHighlights] = useState<[number, number][]>([]);
  const [filter, setFilter] = useState<"all" | "NG" | "WARNING" | "OK">("all");
  const [openChecks, setOpenChecks] = useState(new Set<number>());
  const [layers, setLayers] = useState(initialLayers);
  const [criterion, setCriterion] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [searchError, setSearchError] = useState("");
  const [offlineReady, setOfflineReady] = useState(false);
  const [offlineError, setOfflineError] = useState(false);
  const checklistRef = useRef<HTMLDivElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const focusCriterion = useRef(false);
  const onNavigated = useCallback(() => setTarget(null), []);

  useEffect(() => {
    let cancelled = false;
    loadManifest().then((data) => {
      if (cancelled) return;
      setManifest(data);
      setActiveId(data.floors[0].id);
      setError("");
    }).catch((e: Error) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [retry]);

  useEffect(() => {
    if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`)
      .then(() => navigator.serviceWorker.ready)
      .then(() => setOfflineReady(true))
      .catch(() => setOfflineError(true));
  }, []);

  const floor = manifest?.floors.find((f) => f.id === activeId);
  const drawing = floor ? drawings[floor.id] : undefined;
  const lower = manifest?.floors.find((f) => f.id === floor?.lowerFloorId);
  useEffect(() => {
    if (!floor || view !== "drawing") return;
    let cancelled = false;
    const wanted = [floor, ...(layers.lowerWall && lower ? [lower] : [])];
    Promise.all(wanted.map(async (f) => [f.id, await loadDrawing(f)] as const))
      .then((entries) => { if (!cancelled) { setDrawings((prev) => ({ ...prev, ...Object.fromEntries(entries) })); setDrawingError(""); } })
      .catch((e: Error) => { if (!cancelled) setDrawingError(e.message); });
    return () => { cancelled = true; };
  }, [floor, lower, view, layers.lowerWall, drawingRetry]);

  useEffect(() => {
    if (criterion !== null && view === "checklist") {
      const element = checklistRef.current?.querySelector<HTMLElement>(`#criterion-${criterion}`);
      element?.scrollIntoView({ block: "center" });
      if (focusCriterion.current) element?.focus({ preventScroll: true });
      focusCriterion.current = false;
    }
  }, [criterion, view]);

  useEffect(() => {
    if (view === "drawing" && sidebarRef.current) sidebarRef.current.scrollTop = 0;
  }, [view, selectedResult, selected?.id, activeId]);

  const openCriterion = (id: number) => { focusCriterion.current = true; setCriterion(id); setView("checklist"); };
  const navigate = (coords: [number, number], sleeveId?: string, points?: [number, number][], result?: CheckResult) => {
    setDrawingError("");
    setSelected(floor?.sleeves.find((s) => s.id === sleeveId) ?? null);
    setSelectedResult(result ?? null);
    setLayers({ ...initialLayers,
      dim: !result || [4, 9, 10, 11, 12, 13].includes(result.check_id),
      lowerWall: result?.check_id === 6 && !!lower,
    });
    setHighlights(points ?? []);
    setTarget(coords);
    setView("drawing");
  };
  const openOverview = (result?: CheckResult) => {
    setDrawingError("");
    setSelected(null); setSelectedResult(result ?? null); setTarget(null); setHighlights([]);
    setLayers(initialLayers); setView("drawing");
  };

  if (!manifest || !floor) return <main role="status" style={{ padding: 20, fontSize: 13, color: "#6b7280" }}>
    <p>{error || "図面とチェック結果を読み込み中…"}</p>
    {error && <button style={buttonStyle} onClick={() => setRetry((n) => n + 1)}>読み込み直す</button>}
  </main>;

  const ngCount = floor.results.filter((r) => r.severity === "NG").length;
  const warnCount = floor.results.filter((r) => r.severity === "WARNING").length;
  const counts = { 衛生: 0, 空調: 0, 電気: 0, その他: 0 };
  for (const s of floor.sleeves) counts[s.discipline in counts ? s.discipline as keyof typeof counts : "その他"]++;
  const searchSleeve = () => {
    const number = search.trim().match(/(?:P-?N-?)?(\d+)$/i)?.[1];
    const sleeve = number ? floor.sleeves.find((s) => s.pn_number?.toUpperCase() === `P-N-${Number(number)}`) : null;
    if (sleeve) { navigate(sleeve.center, sleeve.id); setSearchError(""); }
    else setSearchError("この図面に該当する番号がありません");
  };

  return <div className="print-root" style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#f8fafc", color: "#111827", fontFamily: "'Inter', 'Noto Sans JP', -apple-system, sans-serif" }}>
    <header className="no-print" style={{ background: "#fff", borderBottom: "1px solid #e5e7eb", padding: "10px 20px", display: "flex", alignItems: "center", gap: 12 }}>
      <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: -0.3, whiteSpace: "nowrap" }}>AI施工図確認</span>
      <nav role="tablist" aria-label="表示切り替え" style={{ display: "inline-flex", background: "#f3f4f6", borderRadius: 7, padding: 2, gap: 2, marginLeft: 12, flexShrink: 0 }}>
        {tabs.map(([mode, label], index) => <button key={mode} id={`tab-${mode}`} role="tab" aria-controls="demo-panel"
          aria-selected={view === mode} tabIndex={view === mode ? 0 : -1} onClick={() => setView(mode)}
          onKeyDown={(e) => {
            const next = e.key === "ArrowRight" ? (index + 1) % tabs.length : e.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : null;
            if (next !== null) { e.preventDefault(); setView(tabs[next][0]); document.getElementById(`tab-${tabs[next][0]}`)?.focus(); }
          }}
          style={{ padding: "4px 14px", border: "none", borderRadius: 5, cursor: "pointer", fontSize: 12, fontWeight: view === mode ? 500 : 400, background: view === mode ? "#111827" : "transparent", color: view === mode ? "#fff" : "#9ca3af", whiteSpace: "nowrap" }}>{label}</button>)}
      </nav>
      <span style={{ marginLeft: 8, color: "#6b7280", fontSize: 12, whiteSpace: "nowrap" }}>チェック済み</span>
      <form onSubmit={(e) => { e.preventDefault(); searchSleeve(); }} style={{ display: "inline-flex", alignItems: "center", gap: 6, marginLeft: 12 }}>
        <input aria-label="P-N番号で検索" value={search} placeholder="P-N番号で検索 (例 12)"
          onChange={(e) => { setSearch(e.target.value); setSearchError(""); }}
          style={{ padding: "5px 10px", fontSize: 12, width: 160, border: `1px solid ${searchError ? "#dc2626" : "#d1d5db"}`, borderRadius: 6, background: searchError ? "#fef2f2" : "#fff" }} />
      </form>
      <button onClick={() => window.print()} style={{ ...buttonStyle, padding: "5px 12px" }}>PDF出力</button>
    </header>
    <div className="no-print" style={{ background: "#fff", borderBottom: "1px solid #e5e7eb", padding: "6px 20px", display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{ display: "inline-flex", background: "#f3f4f6", borderRadius: 7, padding: 2, gap: 2 }}>
        {manifest.floors.map((f) => <button key={f.id} aria-pressed={f.id === activeId}
          onClick={() => { setActiveId(f.id); setDrawingError(""); setSelected(null); setSelectedResult(null); setTarget(null); setHighlights([]); setSearch(""); setSearchError(""); setOpenChecks(new Set()); setLayers(initialLayers); }}
          style={{ padding: "4px 16px", border: "none", borderRadius: 5, cursor: "pointer", fontSize: 12, fontWeight: activeId === f.id ? 500 : 400, background: activeId === f.id ? "#fff" : "transparent", color: activeId === f.id ? "#111827" : "#9ca3af", boxShadow: activeId === f.id ? "0 1px 2px rgba(0,0,0,0.06)" : "none", display: "inline-flex", alignItems: "center", gap: 6 }}>
          {f.label}<span style={{ fontSize: 9, fontWeight: 600, padding: "1px 5px", borderRadius: 3, background: "#f3f4f6", color: "#6b7280", letterSpacing: 0.3 }}>DXF</span>
        </button>)}
      </div>
      <button type="button" disabled title="図面追加（表示のみ）" style={{ ...buttonStyle, cursor: "default", whiteSpace: "nowrap" }}>＋ 図面を追加</button>
      <span role="status" style={{ marginLeft: "auto", color: "#9ca3af", fontSize: 11 }}>{offlineReady ? "オフライン利用準備済み" : offlineError ? "オフライン保存できませんでした" : import.meta.env.PROD && "serviceWorker" in navigator ? "オフライン利用の準備中…" : ""}</span>
    </div>
    <div className="no-print" style={{ padding: "5px 20px", background: "#fff", borderBottom: "1px solid #e5e7eb", color: "#6b7280", fontSize: 11 }}>
      工事前に、スリーブ図をチェックリストで確かめるデモ
      {searchError && <span role="alert" style={{ marginLeft: 16, color: "#dc2626" }}>{searchError}</span>}
    </div>
    <main style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <div className="no-print" style={{ background: "#f9fafb", borderBottom: "1px solid #e5e7eb", padding: "4px 16px", fontSize: 11, color: "#6b7280", display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <span>現在表示中:</span><span style={{ fontWeight: 600, color: "#111827" }}>{floor.label}</span>
        <span style={{ fontSize: 9, fontWeight: 600, padding: "1px 5px", borderRadius: 3, background: "#f3f4f6" }}>DXF</span>
        <button onClick={() => { setCriterion(null); setView("checklist"); }} style={{ marginLeft: "auto", border: "none", background: "none", fontSize: 11, color: "#6b7280", textDecoration: "underline", cursor: "pointer" }}>照合: {manifest.checklistName}（#2〜#14）</button>
      </div>
      <div id="demo-panel" role="tabpanel" aria-labelledby={`tab-${view}`} style={{ flex: 1, overflow: "hidden", display: "flex" }}>
        {view === "list" && <section aria-label="チェック結果一覧" style={{ flex: 1, overflow: "auto" }}>
          <ListView floorData={listFloorData(floor)} results={floor.results} checkDefs={manifest.checks}
            filter={filter} onFilterChange={setFilter} openChecks={openChecks} onOpenChecksChange={setOpenChecks}
            onNavigate={navigate} onOpenDrawing={openOverview} onOpenCriterion={openCriterion} />
        </section>}
        {view === "checklist" && <section aria-label="チェック観点" style={{ flex: 1, display: "flex", flexDirection: "column", background: "#fff", minWidth: 0 }}>
          <div style={{ padding: "16px 20px 12px", borderBottom: "1px solid #d1d5db" }}>
            <div style={{ maxWidth: 1120, margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 16 }}>
              <div><h2 style={{ fontSize: 18, fontWeight: 700, color: "#111827", marginBottom: 5 }}>{manifest.checklistName}</h2>
                <p style={{ fontSize: 13, color: "#475569" }}>図面のチェックに使う項目と判定基準</p></div>
              <p style={{ fontSize: 12, color: "#475569", whiteSpace: "nowrap" }}>{manifest.checks.filter((d) => d.enabled).length} 項目 · チェック済み {new Date(manifest.generatedAt).toLocaleDateString("ja-JP")}</p>
            </div>
          </div>
          <div ref={checklistRef} style={{ flex: 1, overflow: "auto", padding: "0 20px 24px", minHeight: 0 }}>
            <table className="criteria-table" aria-label="チェック項目と判定基準">
              <colgroup><col style={{ width: 64 }} /><col style={{ width: "22%" }} /><col /></colgroup>
              <thead><tr><th scope="col">番号</th><th scope="col">チェック項目</th><th scope="col">判定基準</th></tr></thead>
              <tbody>{manifest.checks.filter((d) => d.enabled).map((def) => <tr key={def.id} id={`criterion-${def.id}`} tabIndex={-1} aria-current={criterion === def.id ? "true" : undefined}>
                <td className="criterion-number">#{def.id}</td>
                <th scope="row">{def.name}</th>
                <td>{def.description}</td>
              </tr>)}</tbody>
            </table>
            <p style={{ maxWidth: 1120, margin: "14px auto 0", fontSize: 12, color: "#475569", lineHeight: 1.7 }}>{manifest.checklistNote}</p>
          </div>
        </section>}
        {view === "data" && <Suspense fallback={<p style={{ padding: 20, fontSize: 12, color: "#9ca3af" }}>図面データを読み込み中…</p>}>
          <DemoDataView key={floor.id} floor={floor} onNavigate={navigate} />
        </Suspense>}
        {(view === "drawing" || drawing) && <div style={{ display: view === "drawing" ? "flex" : "none", flex: 1, minWidth: 0 }}>
          <section className="drawing-panel" aria-label="スリーブ図面" style={{ flex: 1, overflow: "hidden", minWidth: 0 }}>
            {drawingError ? <div role="alert" style={{ padding: 20, fontSize: 13 }}>{drawingError}<button style={{ ...buttonStyle, marginLeft: 12 }} onClick={() => { setDrawingError(""); setDrawingRetry((n) => n + 1); }}>再読み込み</button></div>
              : drawing ? <Suspense fallback={<p style={{ padding: 20, fontSize: 13, color: "#9ca3af" }}>図面を表示中…</p>}><DrawingView
                key={floor.id} floorData={drawing} lowerFloorData={layers.lowerWall && lower ? drawings[lower.id] ?? null : null}
                results={floor.results} onSleeveHover={noop} onSleeveClick={(s) => { setSelected(s); setSelectedResult(null); }}
                selectedSleeveId={selected?.id ?? null} layers={layers} sleeveFilters={sleeveFilters}
                navigateTarget={target} onNavigated={onNavigated} highlightCoords={highlights}
                onToggleLayer={(key) => setLayers((prev) => ({ ...prev, [key]: !prev[key] }))}
                onToggleLayerGroup={(keys) => setLayers((prev) => { const on = !keys.every((key) => prev[key]); return { ...prev, ...Object.fromEntries(keys.map((key) => [key, on])) }; })}
                onToggleSleeveFilter={noop} sleeveCounts={counts} showLowerWallToggle={!!lower} lowerFloorLabel="下階"
                onPdfFilesSelected={noop} onPdfClear={noop} onPdfOpacityChange={noop} simplified />
              </Suspense> : <p style={{ padding: 20, fontSize: 13, color: "#9ca3af" }}>図面を読み込み中…</p>}
          </section>
          <aside ref={sidebarRef} className="drawing-sidebar no-print" aria-label="図面の詳細" style={{ width: 300, borderLeft: "1px solid #e5e7eb", background: "#fff", overflow: "auto", flexShrink: 0 }}>
            {selectedResult && <FocusedCheckResult result={selectedResult}
              rule={manifest.checks.find((def) => def.id === selectedResult.check_id)?.description}
              additionalResults={selected ? floor.results.filter((r) => r !== selectedResult && r.sleeve_id === selected.id && r.check_id === selectedResult.check_id) : []}
              onOpenCriterion={openCriterion} />}
            {selected || selectedResult ? <button onClick={() => { setSelected(null); setSelectedResult(null); }} style={{ margin: "10px 16px 0", border: "none", background: "none", color: "#6b7280", cursor: "pointer", fontSize: 11 }}>← 図面の要約</button> : null}
            {selected ? <SleeveInfo sleeve={selected} results={floor.results} slabLabels={drawing?.slab_labels} onOpenCriterion={openCriterion} focusedCheckId={selectedResult?.check_id} checkDefs={manifest.checks} />
              : selectedResult ? null
              : <div style={{ padding: 20, color: "#6b7280", fontSize: 13, lineHeight: 1.7 }}>
                <div style={{ fontWeight: 600, color: "#111827", marginBottom: 12 }}>図面の要約</div>
                <dl className="drawing-stats" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 6, marginBottom: 16 }}>
                  <dt>スリーブ</dt><dd>{floor.sleeves.length} 個</dd>
                  <dt>NG</dt><dd style={{ color: "#dc2626" }}>{ngCount} 件</dd>
                  <dt>要確認</dt><dd style={{ color: "#d97706" }}>{warnCount} 件</dd>
                </dl>
                <p style={{ fontSize: 11, marginBottom: 12 }}>件数はチェック結果の数です。同じスリーブに複数の指摘がある場合があります。</p>
                <p>スリーブをタップすると、<br />詳細が表示されます。</p>
              </div>}
          </aside>
        </div>}
      </div>
    </main>
  </div>;
}
