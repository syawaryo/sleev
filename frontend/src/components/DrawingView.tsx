import { useMemo, useState, useRef, useCallback, useEffect, memo } from "react";
import type { FloorData, Sleeve, CheckResult } from "../types";

interface Props {
  floorData: FloorData;
  lowerFloorData: FloorData | null;
  results: CheckResult[];
  onSleeveHover: (sleeve: Sleeve | null) => void;
  onSleeveClick: (sleeve: Sleeve | null) => void;
  selectedSleeveId: string | null;
  layers: { grid: boolean; wall: boolean; outerWall: boolean; step: boolean; recess: boolean; column: boolean; sleeve: boolean; dim: boolean; lowerWall: boolean; slabLevel: boolean; raw: boolean };
  sleeveFilters: { 衛生: boolean; 空調: boolean; 電気: boolean; その他: boolean };
  colorMode: "severity" | "fl" | "discipline";
  pdfOverlayUrl?: string | null;
  pdfOverlayOpacity?: number;
  navigateTarget?: [number, number] | null;
  onNavigated?: () => void;
  highlightCoords?: [number, number][];
}

const SEVERITY_COLORS: Record<string, { stroke: string; fill: string }> = {
  NG: { stroke: "#dc2626", fill: "#fef2f2" },
  WARNING: { stroke: "#d97706", fill: "#fffbeb" },
  OK: { stroke: "#16a34a", fill: "#dcfce7" },
};

const FL_COLORS: Record<string, string> = {
  "FL-225": "#3b82f6",
  "FL-175": "#8b5cf6",
  "FL-750": "#ec4899",
  "FL-765": "#d946ef",
  "FL+40": "#f59e0b",
  "FL+0": "#84cc16",
  "FL-60": "#06b6d4",
};

const DISC_COLORS: Record<string, string> = {
  "衛生": "#3b82f6",
  "空調": "#f59e0b",
  "電気": "#ef4444",
  "建築": "#6b7280",
};

const INITIAL_VB = { x: -5000, y: -40000, w: 90000, h: 45000 };
const MIN_ZOOM_W = 5000;
const MAX_ZOOM_W = 500000;

type ViewBox = { x: number; y: number; w: number; h: number };
type DataBounds = { minX: number; maxX: number; minY: number; maxY: number };
type LayersState = Props["layers"];
type SleeveFilters = Props["sleeveFilters"];
type SeverityMap = Map<string, "NG" | "WARNING" | "OK">;

// ---------------------------------------------------------------------------
// Static layers — grid, walls, dims, slab, P-N labels.
// Only re-renders when floorData / lowerFloorData / layers / dataBounds change.
// ---------------------------------------------------------------------------

interface StaticLayersProps {
  floorData: FloorData;
  lowerFloorData: FloorData | null;
  layers: LayersState;
  dataBounds: DataBounds | null;
}

const StaticLayers = memo(function StaticLayers({
  floorData, lowerFloorData, layers,
}: StaticLayersProps) {
  // Pre-compute outer-wall classification once (regex in render loop is wasteful).
  const wallIsOuter = useMemo(
    () => floorData.wall_lines.map(w => w.wall_type === "外壁" || /外壁/.test(w.layer)),
    [floorData.wall_lines]
  );

  // Grid envelope from the axes themselves — walls/dims can extend past the
  // building, so deriving from dataBounds would stretch axes and bubble
  // positions far beyond the actual grid.
  const gridFrame = useMemo(() => {
    const vPos = floorData.grid_lines.filter(g => g.direction === "V").map(g => g.position);
    const hPos = floorData.grid_lines.filter(g => g.direction === "H").map(g => g.position);
    if (vPos.length === 0 || hPos.length === 0) return null;
    const overhang = 2000;  // 2m overshoot past the outermost grid
    return {
      x1: Math.min(...vPos) - overhang,
      x2: Math.max(...vPos) + overhang,
      y1: Math.min(...hPos) - overhang,
      y2: Math.max(...hPos) + overhang,
      bubbleR: 900,
    };
  }, [floorData.grid_lines]);

  // Raw passthrough rendering — every LINE / LWPOLYLINE / ARC / CIRCLE that
  // didn't get picked up by a typed extractor. One <path> per layer keeps the
  // SVG tree compact (~100 elements) even when the underlying DXF has tens of
  // thousands of segments.
  const rawPathsByLayer = useMemo(() => {
    const raw = floorData.raw_lines || [];
    if (raw.length === 0) return [] as { layer: string; d: string }[];
    const groups = new Map<string, string[]>();
    for (const r of raw) {
      if (r.points.length < 2) continue;
      const [x0, y0] = r.points[0];
      const parts = [`M${x0.toFixed(1)} ${y0.toFixed(1)}`];
      for (let i = 1; i < r.points.length; i++) {
        const [x, y] = r.points[i];
        parts.push(`L${x.toFixed(1)} ${y.toFixed(1)}`);
      }
      const list = groups.get(r.layer) || [];
      list.push(parts.join(" "));
      groups.set(r.layer, list);
    }
    return Array.from(groups.entries()).map(([layer, ds]) => ({
      layer, d: ds.join(" "),
    }));
  }, [floorData.raw_lines]);

  return (
    <>
      {/* Raw DXF passthrough — behind everything else, faint grey */}
      {layers.raw && rawPathsByLayer.map(({ layer, d }) => (
        <path key={`raw-${layer}`} d={d}
          fill="none" stroke="#cbd5e1" strokeWidth={8} opacity={0.55} />
      ))}
      {layers.raw && (floorData.raw_texts || []).map((t, i) => (
        <g key={`rawt-${i}`} transform={`translate(${t.x},${t.y}) scale(1,-1)${t.rotation ? ` rotate(${-t.rotation})` : ""}`}>
          <text x={0} y={0} fontSize={Math.max(t.height || 250, 250)}
                fill="#475569" fontFamily="'Noto Sans JP',sans-serif">{t.text}</text>
        </g>
      ))}

      {/* Grid lines + axis-label bubbles — drawn as 一点鎖線 (chain-dot),
          darker than walls so they read as the drawing's skeleton. */}
      {layers.grid && gridFrame && floorData.grid_lines.flatMap((g, i) => {
        const { x1, x2, y1, y2, bubbleR } = gridFrame;
        const endpoints: [number, number][] = g.direction === "H"
          ? [[x1 - bubbleR, g.position], [x2 + bubbleR, g.position]]
          : [[g.position, y1 - bubbleR], [g.position, y2 + bubbleR]];
        // 一点鎖線 pattern: long-dash, short gap, dot, short gap.
        // Values are in SVG user units (mm). Tuned so the pattern shows
        // cleanly at typical zoom levels.
        const chainDot = "800 150 30 150";
        const line = g.direction === "H" ? (
          <line key={`gh${i}`} x1={x1} y1={g.position} x2={x2} y2={g.position}
            stroke="#1f2937" strokeWidth={22} strokeDasharray={chainDot} opacity={0.75} />
        ) : (
          <line key={`gv${i}`} x1={g.position} y1={y1} x2={g.position} y2={y2}
            stroke="#1f2937" strokeWidth={22} strokeDasharray={chainDot} opacity={0.75} />
        );
        const bubbles = endpoints.map(([lx, ly], pi) => (
          <g key={`gl${i}-${pi}`} transform={`translate(${lx} ${ly})`}>
            <circle cx={0} cy={0} r={bubbleR} fill="#fff" stroke="#111827" strokeWidth={35} />
            <text x={0} y={0} textAnchor="middle" dominantBaseline="central"
                  fontSize={bubbleR * 1.2} fill="#111827" fontWeight={700}
                  fontFamily="'Inter','Noto Sans JP',sans-serif"
                  transform="scale(1,-1)">{g.axis_label}</text>
          </g>
        ));
        return [line, ...bubbles];
      })}

      {/* Lower floor walls (1F wall overlay on 2F) */}
      {layers.lowerWall && lowerFloorData?.wall_lines.map((w, i) => (
        <line key={`lw${i}`} x1={w.start[0]} y1={w.start[1]} x2={w.end[0]} y2={w.end[1]}
          stroke="#8b5cf6" strokeWidth={40} opacity={0.4} />
      ))}

      {/* Walls */}
      {floorData.wall_lines.map((w, i) => {
        const isOuter = wallIsOuter[i];
        const visible = isOuter ? layers.outerWall : layers.wall;
        if (!visible) return null;
        return (
          <line key={`w${i}`} x1={w.start[0]} y1={w.start[1]} x2={w.end[0]} y2={w.end[1]}
            stroke={isOuter ? "#111827" : "#64748b"}
            strokeWidth={isOuter ? 55 : 25}
            strokeLinecap={isOuter ? "round" : undefined} />
        );
      })}

      {/* Recess polygons (床ヌスミ) — rendered as translucent fills so they read
          as "floor depressions" rather than "step lines". */}
      {layers.recess && floorData.recess_polygons?.map((rp, i) => {
        const d = rp.vertices.length
          ? "M " + rp.vertices.map(([x, y]) => `${x} ${y}`).join(" L ") + " Z"
          : "";
        if (!d) return null;
        return (
          <path key={`r${i}`} d={d}
            fill="#0ea5e9" fillOpacity={0.22}
            stroke="#0369a1" strokeWidth={15} strokeOpacity={0.7}
            strokeDasharray="60 30" />
        );
      })}

      {/* Step lines — FL-verified: hide "spurious" (same FL both sides),
          dim "unknown" so the eye focuses on confirmed steps. */}
      {layers.step && floorData.step_lines.map((s, i) => {
        if (s.fl_status === "spurious") return null;
        const opacity = s.fl_status === "real" ? 0.9 : 0.5;
        return (
          <line key={`s${i}`} x1={s.start[0]} y1={s.start[1]} x2={s.end[0]} y2={s.end[1]}
            stroke="#d97706" strokeWidth={25} opacity={opacity} />
        );
      })}

      {/* Column / wall-finish lines */}
      {layers.column && floorData.column_lines.map((c, i) => (
        <line key={`col${i}`} x1={c.start[0]} y1={c.start[1]} x2={c.end[0]} y2={c.end[1]}
          stroke="#7c3aed" strokeWidth={20} opacity={0.6} />
      ))}

      {/* Dimension lines */}
      {layers.dim && floorData.dim_lines.map((d, i) => {
        const val = Math.round(d.measurement);
        if (val < 1) return null;

        const x1 = d.defpoint2[0], y1 = d.defpoint2[1];
        const x2 = d.defpoint3[0], y2 = d.defpoint3[1];

        let isHorizontal: boolean;
        if (d.angle !== null && d.angle !== undefined) {
          const normAngle = ((d.angle % 360) + 360) % 360;
          isHorizontal = normAngle < 45 || normAngle > 315 || (normAngle > 135 && normAngle < 225);
        } else {
          const dx = Math.abs(x2 - x1);
          const dy = Math.abs(y2 - y1);
          isHorizontal = dx >= dy;
        }

        let dlx1: number, dly1: number, dlx2: number, dly2: number;
        if (isHorizontal) {
          dly1 = d.defpoint1[1]; dly2 = d.defpoint1[1];
          dlx1 = x1; dlx2 = x2;
        } else {
          dlx1 = d.defpoint1[0]; dlx2 = d.defpoint1[0];
          dly1 = y1; dly2 = y2;
        }

        const mx = (dlx1 + dlx2) / 2;
        const my = (dly1 + dly2) / 2;

        return (
          <g key={`dm${i}`}>
            <line x1={x1} y1={y1} x2={dlx1} y2={dly1}
                  stroke="#06b6d4" strokeWidth={5} opacity={0.3} />
            <line x1={x2} y1={y2} x2={dlx2} y2={dly2}
                  stroke="#06b6d4" strokeWidth={5} opacity={0.3} />
            <line x1={dlx1} y1={dly1} x2={dlx2} y2={dly2}
                  stroke="#06b6d4" strokeWidth={10} opacity={0.5} />
            <circle cx={dlx1} cy={dly1} r={20} fill="#06b6d4" opacity={0.5} />
            <circle cx={dlx2} cy={dly2} r={20} fill="#06b6d4" opacity={0.5} />
            <g transform={`translate(${mx},${my})`}>
              <g transform="scale(1,-1)">
                <text x={0} y={0} fontSize={120} fill="#06b6d4" fontWeight={600}
                  textAnchor="middle" opacity={0.7}>
                  {val}
                </text>
              </g>
            </g>
          </g>
        );
      })}

      {/* Slab outlines */}
      {layers.slabLevel && floorData.slab_outlines?.map((s, i) => (
        <line key={`so${i}`} x1={s.start[0]} y1={s.start[1]} x2={s.end[0]} y2={s.end[1]}
          stroke="#4338ca" strokeWidth={18} opacity={0.5} />
      ))}

      {/* Slab info labels */}
      {layers.slabLevel && floorData.slab_labels?.map((sl, i) => (
        <g key={`slab${i}`} transform={`translate(${sl.x},${sl.y})`}>
          <g transform="scale(1,-1)">
            <text x={0} y={-120} fontSize={200} fill="#4338ca" fontWeight={700} textAnchor="middle" opacity={0.8}>
              {sl.slab_no}
            </text>
            <text x={0} y={100} fontSize={150} fill="#6366f1" fontWeight={500} textAnchor="middle" opacity={0.7}>
              FL{sl.level}
            </text>
            {sl.thickness && (
              <text x={0} y={300} fontSize={130} fill="#818cf8" fontWeight={400} textAnchor="middle" opacity={0.6}>
                t={sl.thickness}
              </text>
            )}
          </g>
        </g>
      ))}

      {/* Step level labels */}
      {layers.slabLevel && floorData.slab_zones?.map((z, i) => (
        <g key={`sl${i}`} transform={`translate(${z.x},${z.y})`}>
          <g transform="scale(1,-1)">
            <text x={0} y={0} fontSize={160} fill="#d97706" fontWeight={600} textAnchor="middle" opacity={0.7}>
              FL{z.fl_value >= 0 ? "+" : ""}{z.fl_value}
            </text>
          </g>
        </g>
      ))}

      {/* P-N number labels + arrow lines (gated with sleeve layer — same visual group) */}
      {layers.sleeve && floorData.pn_labels?.map((pn, i) => (
        <g key={`pn${i}`}>
          {pn.arrow_verts && pn.arrow_verts.length === 2 && (
            <line
              x1={pn.arrow_verts[0][0]} y1={pn.arrow_verts[0][1]}
              x2={pn.arrow_verts[1][0]} y2={pn.arrow_verts[1][1]}
              stroke="#e11d48" strokeWidth={12} opacity={0.6}
            />
          )}
          <g transform={`translate(${pn.x},${pn.y})`}>
            <g transform="scale(1,-1)">
              <text x={0} y={0} fontSize={150} fill="#e11d48" fontWeight={700} textAnchor="middle" opacity={0.8}>
                {pn.text}
              </text>
            </g>
          </g>
        </g>
      ))}
    </>
  );
});

// ---------------------------------------------------------------------------
// Sleeve layer — interactive sleeves. Re-renders on selection/results/mode change,
// NOT on hover (because hover state lives in the parent, never passed down here).
// ---------------------------------------------------------------------------

function getSleeveColors(
  s: Sleeve,
  colorMode: Props["colorMode"],
  severityMap: SeverityMap,
): { stroke: string; fill: string } {
  if (colorMode === "fl") {
    const c = FL_COLORS[s.fl_text || ""] || "#9ca3af";
    return { stroke: c, fill: c + "20" };
  }
  if (colorMode === "discipline") {
    const c = DISC_COLORS[s.discipline] || "#9ca3af";
    return { stroke: c, fill: c + "20" };
  }
  return SEVERITY_COLORS[severityMap.get(s.id) || "OK"];
}

interface SleeveLayerProps {
  sleeves: Sleeve[];
  sleeveFilters: SleeveFilters;
  colorMode: Props["colorMode"];
  severityMap: SeverityMap;
  selectedSleeveId: string | null;
  onSleeveHover: (s: Sleeve | null) => void;
  onSleeveClick: (s: Sleeve | null) => void;
  visible: boolean;
}

const SleeveLayer = memo(function SleeveLayer({
  sleeves, sleeveFilters, colorMode, severityMap, selectedSleeveId, onSleeveHover, onSleeveClick, visible,
}: SleeveLayerProps) {
  const filtered = useMemo(() => {
    return sleeves.filter(s => {
      const disc = s.discipline as keyof SleeveFilters;
      if (disc in sleeveFilters) return sleeveFilters[disc];
      return sleeveFilters["その他"];
    });
  }, [sleeves, sleeveFilters]);

  if (!visible) return null;

  return (
    <>
      {filtered.map((s) => {
        const colors = getSleeveColors(s, colorMode, severityMap);
        const isSelected = s.id === selectedSleeveId;
        const isRect = s.shape === "rect";
        // Render at the drawing's true dimensions. Previously we clamped
        // everything to 200 mm half-size for click ergonomics, which blew
        // up small φ60 / φ124 pipes into giant blobs. The hit area below
        // is still padded so small sleeves remain clickable.
        const halfW = (s.width ?? s.diameter) / 2;
        const halfH = (s.height ?? s.diameter) / 2;
        const r = s.diameter / 2;
        // Hit area: always at least 300 mm half-size so even φ60 stays
        // clickable. Drawn transparently, does not affect the visible glyph.
        const hitR = Math.max(Math.max(halfW, halfH, r) * 1.8, 300);
        const cx = s.center[0];
        const cy = s.center[1];
        return (
          <g key={s.id} style={{ cursor: "pointer" }}
            onMouseEnter={(e) => { e.stopPropagation(); onSleeveHover(s); }}
            onClick={(e) => { e.stopPropagation(); onSleeveClick(s); }}>
            <circle cx={cx} cy={cy} r={hitR} fill="transparent" stroke="none" />
            {isSelected && (
              <>
                <circle cx={cx} cy={cy} r={r + 200}
                  fill="none" stroke="#ef4444" strokeWidth={25} opacity={0.8}>
                  <animate attributeName="r" from={r + 100} to={r + 400} dur="1s" repeatCount="indefinite" />
                  <animate attributeName="opacity" from="0.8" to="0" dur="1s" repeatCount="indefinite" />
                </circle>
                <circle cx={cx} cy={cy} r={r + 80}
                  fill="none" stroke="#ef4444" strokeWidth={20} strokeDasharray="60,30" opacity={0.7} />
              </>
            )}
            {isRect ? (
              <rect
                x={cx - halfW} y={cy - halfH}
                width={halfW * 2} height={halfH * 2}
                fill={colors.fill} stroke={colors.stroke}
                strokeWidth={isSelected ? 35 : 20}
              />
            ) : (
              <circle cx={cx} cy={cy} r={r}
                fill={colors.fill} stroke={colors.stroke} strokeWidth={isSelected ? 35 : 20} />
            )}
            <circle cx={cx} cy={cy} r={35} fill={colors.stroke} />
          </g>
        );
      })}
    </>
  );
});

// ---------------------------------------------------------------------------
// Highlight layer — pulsing markers from list navigation. Tiny.
// ---------------------------------------------------------------------------

interface HighlightLayerProps {
  coords: [number, number][];
}

const HighlightLayer = memo(function HighlightLayer({ coords }: HighlightLayerProps) {
  if (!coords || coords.length === 0) return null;
  return (
    <>
      {coords.map((c, i) => (
        <g key={`hl${i}`}>
          <circle cx={c[0]} cy={c[1]} r={300}
            fill="none" stroke="#ef4444" strokeWidth={30} opacity={0.9}>
            <animate attributeName="r" from="200" to="500" dur="1s" repeatCount="indefinite" />
            <animate attributeName="opacity" from="0.9" to="0" dur="1s" repeatCount="indefinite" />
          </circle>
          <circle cx={c[0]} cy={c[1]} r={150}
            fill="#ef4444" opacity={0.4} />
        </g>
      ))}
    </>
  );
});

// ---------------------------------------------------------------------------
// Main DrawingView — owns viewport state; delegates rendering to memo'd children.
// ---------------------------------------------------------------------------

function DrawingViewInner({
  floorData, lowerFloorData, results, onSleeveHover, onSleeveClick,
  selectedSleeveId, layers, sleeveFilters, colorMode, navigateTarget, onNavigated, highlightCoords,
  pdfOverlayUrl, pdfOverlayOpacity = 0.4,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [vb, setVb] = useState<ViewBox>(INITIAL_VB);
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef<{ x: number; y: number; vb: ViewBox } | null>(null);

  // Bounds of all drawable entities (loop — spread on 10k+ args overflows the stack).
  const dataBounds = useMemo<DataBounds | null>(() => {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    let has = false;
    const addX = (x: number) => {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      has = true;
    };
    const addY = (y: number) => {
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      has = true;
    };
    for (const s of floorData.sleeves) { addX(s.center[0]); addY(s.center[1]); }
    for (const g of floorData.grid_lines) {
      if (g.direction === "H") addY(g.position);
      else addX(g.position);
    }
    for (const w of floorData.wall_lines) {
      addX(w.start[0]); addX(w.end[0]);
      addY(w.start[1]); addY(w.end[1]);
    }
    for (const c of floorData.column_lines) {
      addX(c.start[0]); addX(c.end[0]);
      addY(c.start[1]); addY(c.end[1]);
    }
    for (const o of floorData.slab_outlines || []) {
      addX(o.start[0]); addX(o.end[0]);
      addY(o.start[1]); addY(o.end[1]);
    }
    if (!has) return null;
    return { minX, maxX, minY, maxY };
  }, [floorData]);

  const fitVb = useCallback((): ViewBox => {
    if (!dataBounds) return INITIAL_VB;
    const { minX, maxX, minY, maxY } = dataBounds;
    const pad = 0.08;
    const spanX = (maxX - minX) || MIN_ZOOM_W;
    const spanY = (maxY - minY) || MIN_ZOOM_W;
    const w = Math.min(MAX_ZOOM_W, Math.max(MIN_ZOOM_W, spanX * (1 + pad * 2)));
    const h = Math.min(MAX_ZOOM_W * 0.6, Math.max(MIN_ZOOM_W * 0.5, spanY * (1 + pad * 2)));
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    return { x: cx - w / 2, y: -cy - h / 2, w, h };
  }, [dataBounds]);

  const fittedFloorRef = useRef<unknown>(null);
  useEffect(() => {
    if (floorData !== fittedFloorRef.current && dataBounds) {
      fittedFloorRef.current = floorData;
      setVb(fitVb());
    }
  }, [floorData, dataBounds, fitVb]);

  const vbRef = useRef(vb);
  vbRef.current = vb;

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const rect = svg.getBoundingClientRect();
      const cur = vbRef.current;
      const sx = (e.clientX - rect.left) / rect.width;
      const sy = (e.clientY - rect.top) / rect.height;
      const ptX = cur.x + sx * cur.w;
      const ptY = cur.y + sy * cur.h;
      const delta = Math.sign(e.deltaY) * Math.min(Math.abs(e.deltaY), 100);
      const factor = 1 + delta * 0.003;
      const newW = Math.min(Math.max(cur.w * factor, MIN_ZOOM_W), MAX_ZOOM_W);
      const newH = Math.min(Math.max(cur.h * factor, MIN_ZOOM_W * 0.5), MAX_ZOOM_W * 0.5);
      const ratio = newW / cur.w;
      setVb({
        x: ptX - (ptX - cur.x) * ratio,
        y: ptY - (ptY - cur.y) * ratio,
        w: newW,
        h: newH,
      });
    };
    svg.addEventListener("wheel", handler, { passive: false });
    return () => svg.removeEventListener("wheel", handler);
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsPanning(true);
    panStart.current = { x: e.clientX, y: e.clientY, vb: { ...vb } };
  }, [vb]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning || !panStart.current || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const dx = (e.clientX - panStart.current.x) / rect.width * panStart.current.vb.w;
    const dy = (e.clientY - panStart.current.y) / rect.height * panStart.current.vb.h;
    setVb({ ...panStart.current.vb, x: panStart.current.vb.x - dx, y: panStart.current.vb.y - dy });
  }, [isPanning]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    panStart.current = null;
  }, []);

  const handleDoubleClick = useCallback(() => setVb(fitVb()), [fitVb]);

  // Navigate to target coordinates (from list view click)
  useEffect(() => {
    if (!navigateTarget) return;
    const pts = highlightCoords && highlightCoords.length > 1 ? highlightCoords : [navigateTarget];
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const [x, y] of pts) {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
    const spanX = maxX - minX;
    const spanY = maxY - minY;
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const zoomW = Math.max(15000, spanX + 10000);
    const zoomH = Math.max(7500, spanY + 5000);
    setVb({ x: cx - zoomW / 2, y: -cy - zoomH / 2, w: zoomW, h: zoomH });
    onNavigated?.();
  }, [navigateTarget, onNavigated, highlightCoords]);

  // severity lookup for sleeve coloring
  const severityMap = useMemo<SeverityMap>(() => {
    const map: SeverityMap = new Map();
    for (const r of results) {
      if (r.sleeve_id) {
        const cur = map.get(r.sleeve_id);
        if (!cur || r.severity === "NG" || (r.severity === "WARNING" && cur === "OK")) {
          map.set(r.sleeve_id, r.severity);
        }
      }
    }
    return map;
  }, [results]);

  const viewBox = `${vb.x} ${vb.y} ${vb.w} ${vb.h}`;

  return (
    <svg
      ref={svgRef}
      viewBox={viewBox}
      style={{ width: "100%", height: "100%", background: "#fdfdfe", cursor: isPanning ? "grabbing" : "grab" }}
      xmlns="http://www.w3.org/2000/svg"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onDoubleClick={handleDoubleClick}
    >
      <g transform="scale(1,-1)">
        {/* PDF overlay (optional) — drawn behind everything.
            Nested scale(1,-1) cancels the outer Y-flip so the PDF
            renders upright in world space. */}
        {pdfOverlayUrl && dataBounds && (() => {
          const w = dataBounds.maxX - dataBounds.minX;
          const h = dataBounds.maxY - dataBounds.minY;
          return (
            <g transform={`translate(0 ${dataBounds.minY + dataBounds.maxY}) scale(1,-1)`}>
              <image
                href={pdfOverlayUrl}
                x={dataBounds.minX}
                y={dataBounds.minY}
                width={w}
                height={h}
                opacity={pdfOverlayOpacity}
                preserveAspectRatio="xMidYMid meet"
              />
            </g>
          );
        })()}
        <StaticLayers
          floorData={floorData}
          lowerFloorData={lowerFloorData}
          layers={layers}
          dataBounds={dataBounds}
        />
        <SleeveLayer
          sleeves={floorData.sleeves}
          sleeveFilters={sleeveFilters}
          colorMode={colorMode}
          severityMap={severityMap}
          selectedSleeveId={selectedSleeveId}
          onSleeveHover={onSleeveHover}
          onSleeveClick={onSleeveClick}
          visible={layers.sleeve}
        />
        <HighlightLayer coords={highlightCoords || []} />
      </g>
    </svg>
  );
}

export default memo(DrawingViewInner);
