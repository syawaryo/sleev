import { useMemo, useState, useRef, useCallback, useEffect } from "react";
import type { FloorData, Sleeve, CheckResult, SlabZone } from "../types";

interface Props {
  floorData: FloorData;
  lowerFloorData: FloorData | null;
  results: CheckResult[];
  onSleeveHover: (sleeve: Sleeve | null) => void;
  onSleeveClick: (sleeve: Sleeve | null) => void;
  selectedSleeveId: string | null;
  layers: { grid: boolean; wall: boolean; step: boolean; sleeve: boolean; lowerWall: boolean; heatmap: boolean };
  colorMode: "severity" | "fl" | "discipline";
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

/** Map FL value (mm) to a heatmap color: red=high, green=0, blue=low */
function flValueToColor(val: number): string {
  // Clamp to range [-1500, +200]
  const clamped = Math.max(-1500, Math.min(200, val));
  // Normalize to [0,1] where 0=lowest, 1=highest
  const t = (clamped + 1500) / 1700;

  // Color stops: purple(-1500) -> blue(-700) -> cyan(-300) -> green(0) -> yellow(+50) -> orange(+100) -> red(+200)
  let r: number, g: number, b: number;
  if (t < 0.25) {
    // purple to blue
    const s = t / 0.25;
    r = Math.round(128 * (1 - s));
    g = 0;
    b = Math.round(180 + 75 * s);
  } else if (t < 0.5) {
    // blue to cyan
    const s = (t - 0.25) / 0.25;
    r = 0;
    g = Math.round(200 * s);
    b = 255;
  } else if (t < 0.7) {
    // cyan to green
    const s = (t - 0.5) / 0.2;
    r = 0;
    g = Math.round(200 + 55 * s);
    b = Math.round(255 * (1 - s));
  } else if (t < 0.85) {
    // green to yellow
    const s = (t - 0.7) / 0.15;
    r = Math.round(255 * s);
    g = 255;
    b = 0;
  } else {
    // yellow to red
    const s = (t - 0.85) / 0.15;
    r = 255;
    g = Math.round(255 * (1 - s));
    b = 0;
  }
  return `rgb(${r},${g},${b})`;
}

const INITIAL_VB = { x: -5000, y: -40000, w: 90000, h: 45000 };
const ZOOM_FACTOR = 1.04;
const MIN_ZOOM_W = 5000;
const MAX_ZOOM_W = 200000;

export default function DrawingView({
  floorData, lowerFloorData, results, onSleeveHover, onSleeveClick,
  selectedSleeveId, layers, colorMode,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [vb, setVb] = useState(INITIAL_VB);
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef<{ x: number; y: number; vb: typeof INITIAL_VB } | null>(null);

  // Convert screen coords to SVG coords
  const screenToSvg = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    const sx = (clientX - rect.left) / rect.width;
    const sy = (clientY - rect.top) / rect.height;
    return { x: vb.x + sx * vb.w, y: vb.y + sy * vb.h };
  }, [vb]);

  // Wheel zoom — must use native listener with { passive: false } to prevent page scroll
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

      const factor = e.deltaY > 0 ? ZOOM_FACTOR : 1 / ZOOM_FACTOR;

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

  // Pan (mouse drag)
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return; // left click only
    setIsPanning(true);
    panStart.current = { x: e.clientX, y: e.clientY, vb: { ...vb } };
  }, [vb]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning || !panStart.current || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const dx = (e.clientX - panStart.current.x) / rect.width * panStart.current.vb.w;
    const dy = (e.clientY - panStart.current.y) / rect.height * panStart.current.vb.h;
    setVb({
      ...panStart.current.vb,
      x: panStart.current.vb.x - dx,
      y: panStart.current.vb.y - dy,
    });
  }, [isPanning]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    panStart.current = null;
  }, []);

  // Double click to reset
  const handleDoubleClick = useCallback(() => {
    setVb(INITIAL_VB);
  }, []);

  // Pre-compute heatmap cells (Voronoi-style nearest-zone assignment)
  const heatmapCells = useMemo(() => {
    const zones = floorData.slab_zones;
    if (!zones || zones.length === 0) return [];

    const allX = zones.map(z => z.x);
    const allY = zones.map(z => z.y);
    const minX = Math.min(...allX) - 3000;
    const maxX = Math.max(...allX) + 3000;
    const minY = Math.min(...allY) - 3000;
    const maxY = Math.max(...allY) + 3000;

    const CELL = 800;
    const cols = Math.ceil((maxX - minX) / CELL);
    const rows = Math.ceil((maxY - minY) / CELL);

    const cells: { x: number; y: number; color: string }[] = [];
    for (let row = 0; row < rows; row++) {
      const cy = minY + row * CELL + CELL / 2;
      for (let col = 0; col < cols; col++) {
        const cx = minX + col * CELL + CELL / 2;
        let bestDist = Infinity;
        let bestVal = 0;
        for (const z of zones) {
          const dx = cx - z.x;
          const dy = cy - z.y;
          const d = dx * dx + dy * dy;
          if (d < bestDist) {
            bestDist = d;
            bestVal = z.fl_value;
          }
        }
        cells.push({ x: minX + col * CELL, y: minY + row * CELL, color: flValueToColor(bestVal) });
      }
    }
    return cells;
  }, [floorData.slab_zones]);

  const severityMap = useMemo(() => {
    const map = new Map<string, "NG" | "WARNING" | "OK">();
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

  const getSleeveColors = (s: Sleeve): { stroke: string; fill: string } => {
    if (colorMode === "fl") {
      const c = FL_COLORS[s.fl_text || ""] || "#9ca3af";
      return { stroke: c, fill: c + "20" };
    }
    if (colorMode === "discipline") {
      const c = DISC_COLORS[s.discipline] || "#9ca3af";
      return { stroke: c, fill: c + "20" };
    }
    return SEVERITY_COLORS[severityMap.get(s.id) || "OK"];
  };

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
        {/* Slab level heatmap — Voronoi-style nearest-zone coloring */}
        {layers.heatmap && heatmapCells.length > 0 && (
          <g opacity={0.30}>
            {heatmapCells.map((c, i) => (
              <rect key={`hc${i}`} x={c.x} y={c.y} width={800} height={800}
                fill={c.color} stroke="none" />
            ))}
          </g>
        )}

        {/* Grid lines */}
        {layers.grid && floorData.grid_lines.map((g, i) =>
          g.direction === "H" ? (
            <line key={`gh${i}`} x1={-5000} y1={g.position} x2={85000} y2={g.position}
              stroke="#9ca3af" strokeWidth={15} strokeDasharray="300,150" />
          ) : (
            <line key={`gv${i}`} x1={g.position} y1={-5000} x2={g.position} y2={40000}
              stroke="#9ca3af" strokeWidth={15} strokeDasharray="300,150" />
          )
        )}

        {/* Lower floor walls */}
        {layers.lowerWall && lowerFloorData?.wall_lines.map((w, i) => (
          <line key={`lw${i}`} x1={w.start[0]} y1={w.start[1]} x2={w.end[0]} y2={w.end[1]}
            stroke="#8b5cf6" strokeWidth={40} opacity={0.4} />
        ))}

        {/* Walls */}
        {layers.wall && floorData.wall_lines.map((w, i) => (
          <line key={`w${i}`} x1={w.start[0]} y1={w.start[1]} x2={w.end[0]} y2={w.end[1]}
            stroke="#64748b" strokeWidth={25} />
        ))}

        {/* Step lines */}
        {layers.step && floorData.step_lines.map((s, i) => (
          <line key={`s${i}`} x1={s.start[0]} y1={s.start[1]} x2={s.end[0]} y2={s.end[1]}
            stroke="#d97706" strokeWidth={20} opacity={0.6} />
        ))}

        {/* Sleeves */}
        {layers.sleeve && floorData.sleeves.map((s) => {
          const colors = getSleeveColors(s);
          const isSelected = s.id === selectedSleeveId;
          const r = Math.max(s.diameter / 2, 200);
          return (
            <g key={s.id} style={{ cursor: "pointer" }}
              onMouseEnter={(e) => { e.stopPropagation(); onSleeveHover(s); }}
              onClick={(e) => { e.stopPropagation(); onSleeveClick(s); }}>
              {/* Hit area */}
              <circle cx={s.center[0]} cy={s.center[1]} r={r * 1.8} fill="transparent" stroke="none" />
              {/* Selection ring */}
              {isSelected && (
                <circle cx={s.center[0]} cy={s.center[1]} r={r + 80}
                  fill="none" stroke={colors.stroke} strokeWidth={15} strokeDasharray="60,30" opacity={0.5} />
              )}
              {/* Main circle */}
              <circle cx={s.center[0]} cy={s.center[1]} r={r}
                fill={colors.fill} stroke={colors.stroke} strokeWidth={isSelected ? 35 : 20} />
              {/* Center dot */}
              <circle cx={s.center[0]} cy={s.center[1]} r={35} fill={colors.stroke} />
            </g>
          );
        })}
      </g>
      {/* Heatmap legend (screen-space overlay) */}
      {layers.heatmap && floorData.slab_zones && floorData.slab_zones.length > 0 && (() => {
        const vals = [...new Set(floorData.slab_zones.map(z => z.fl_value))].sort((a, b) => b - a);
        const min = Math.min(...vals);
        const max = Math.max(...vals);
        const steps = 8;
        const legendItems: { val: number; color: string }[] = [];
        for (let i = 0; i < steps; i++) {
          const v = max - (max - min) * i / (steps - 1);
          legendItems.push({ val: Math.round(v), color: flValueToColor(v) });
        }
        return (
          <foreignObject x={vb.x + vb.w * 0.01} y={vb.y + vb.h * 0.02} width={vb.w * 0.12} height={vb.h * 0.4}>
            <div style={{ background: "rgba(255,255,255,0.9)", borderRadius: 6, padding: "6px 8px", fontSize: vb.w * 0.0015, border: "1px solid #e5e7eb" }}>
              <div style={{ fontWeight: 600, marginBottom: 4, color: "#374151" }}>FLレベル</div>
              {legendItems.map((item, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 2 }}>
                  <div style={{ width: vb.w * 0.006, height: vb.w * 0.003, borderRadius: 2, background: item.color, opacity: 0.7 }} />
                  <span style={{ color: "#6b7280" }}>{item.val >= 0 ? `+${item.val}` : item.val}mm</span>
                </div>
              ))}
            </div>
          </foreignObject>
        );
      })()}
    </svg>
  );
}
