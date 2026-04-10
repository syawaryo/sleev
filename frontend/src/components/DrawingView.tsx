import { useMemo, useState, useRef, useCallback, useEffect } from "react";
import type { FloorData, Sleeve, CheckResult } from "../types";

interface Props {
  floorData: FloorData;
  lowerFloorData: FloorData | null;
  results: CheckResult[];
  onSleeveHover: (sleeve: Sleeve | null) => void;
  onSleeveClick: (sleeve: Sleeve | null) => void;
  selectedSleeveId: string | null;
  layers: { grid: boolean; wall: boolean; step: boolean; column: boolean; sleeve: boolean; dim: boolean; lowerWall: boolean; slabLevel: boolean };
  colorMode: "severity" | "fl" | "discipline";
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
const MAX_ZOOM_W = 200000;

export default function DrawingView({
  floorData, lowerFloorData, results, onSleeveHover, onSleeveClick,
  selectedSleeveId, layers, colorMode, navigateTarget, onNavigated, highlightCoords,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [vb, setVb] = useState(INITIAL_VB);
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef<{ x: number; y: number; vb: typeof INITIAL_VB } | null>(null);

  // Wheel zoom
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
      // Scale factor proportional to deltaY for smooth pinch/trackpad zoom
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

  const handleDoubleClick = useCallback(() => setVb(INITIAL_VB), []);

  // Navigate to target coordinates (from list view click)
  // Zoom to fit all highlight coords with padding
  useEffect(() => {
    if (navigateTarget) {
      const pts = highlightCoords && highlightCoords.length > 1 ? highlightCoords : [navigateTarget];
      const xs = pts.map(p => p[0]);
      const ys = pts.map(p => p[1]);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const spanX = maxX - minX;
      const spanY = maxY - minY;
      const cx = (minX + maxX) / 2;
      const cy = (minY + maxY) / 2;
      // Add generous padding (at least 15000 width, or span + 5000 margin on each side)
      const zoomW = Math.max(15000, spanX + 10000);
      const zoomH = Math.max(7500, spanY + 5000);
      setVb({ x: cx - zoomW / 2, y: -cy - zoomH / 2, w: zoomW, h: zoomH });
      onNavigated?.();
    }
  }, [navigateTarget, onNavigated, highlightCoords]);

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
            stroke="#d97706" strokeWidth={25} opacity={0.8} />
        ))}

        {/* Column / wall-finish lines */}
        {layers.column && floorData.column_lines.map((c, i) => (
          <line key={`col${i}`} x1={c.start[0]} y1={c.start[1]} x2={c.end[0]} y2={c.end[1]}
            stroke="#7c3aed" strokeWidth={20} opacity={0.6} />
        ))}

        {/* Dimension lines: defpoint2 → defpoint3 = measured span */}
        {layers.dim && floorData.dim_lines.map((d, i) => {
          const val = Math.round(d.measurement);
          if (val < 1) return null;

          // defpoint2 = 1st ext line origin, defpoint3 = 2nd ext line origin
          // defpoint1 = dimension line position (offset from measurement points)
          // angle = rotation (0/null=horizontal, 90/270=vertical)
          const x1 = d.defpoint2[0], y1 = d.defpoint2[1];
          const x2 = d.defpoint3[0], y2 = d.defpoint3[1];

          // Use angle if available, otherwise detect from defpoints
          let isHorizontal: boolean;
          if (d.angle !== null && d.angle !== undefined) {
            const normAngle = ((d.angle % 360) + 360) % 360;
            isHorizontal = normAngle < 45 || normAngle > 315 || (normAngle > 135 && normAngle < 225);
          } else {
            const dx = Math.abs(x2 - x1);
            const dy = Math.abs(y2 - y1);
            isHorizontal = dx >= dy;
          }

          // Dimension line endpoints (projected to defpoint1 offset)
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
              {/* Extension lines from measurement points to dimension line */}
              <line x1={x1} y1={y1} x2={dlx1} y2={dly1}
                    stroke="#06b6d4" strokeWidth={5} opacity={0.3} />
              <line x1={x2} y1={y2} x2={dlx2} y2={dly2}
                    stroke="#06b6d4" strokeWidth={5} opacity={0.3} />
              {/* Dimension line */}
              <line x1={dlx1} y1={dly1} x2={dlx2} y2={dly2}
                    stroke="#06b6d4" strokeWidth={10} opacity={0.5} />
              {/* Tick marks */}
              <circle cx={dlx1} cy={dly1} r={20} fill="#06b6d4" opacity={0.5} />
              <circle cx={dlx2} cy={dly2} r={20} fill="#06b6d4" opacity={0.5} />
              {/* Measurement text */}
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

        {/* Slab outlines (RC立上り線) */}
        {layers.slabLevel && floorData.slab_outlines?.map((s, i) => (
          <line key={`so${i}`} x1={s.start[0]} y1={s.start[1]} x2={s.end[0]} y2={s.end[1]}
            stroke="#4338ca" strokeWidth={18} opacity={0.5} />
        ))}

        {/* Slab info labels (S16 / FL-60 / t=165) */}
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

        {/* Step level labels (FL-60, FL±0 next to step lines) */}
        {layers.slabLevel && floorData.slab_zones?.map((z, i) => (
          <g key={`sl${i}`} transform={`translate(${z.x},${z.y})`}>
            <g transform="scale(1,-1)">
              <text x={0} y={0} fontSize={160} fill="#d97706" fontWeight={600} textAnchor="middle" opacity={0.7}>
                FL{z.fl_value >= 0 ? "+" : ""}{z.fl_value}
              </text>
            </g>
          </g>
        ))}

        {/* P-N number labels + arrow lines from DXF */}
        {layers.sleeve && floorData.pn_labels?.map((pn, i) => (
          <g key={`pn${i}`}>
            {/* Arrow line: INSERT origin → tip (if arrow exists) */}
            {pn.arrow_verts && pn.arrow_verts.length === 2 && (
              <line
                x1={pn.arrow_verts[0][0]} y1={pn.arrow_verts[0][1]}
                x2={pn.arrow_verts[1][0]} y2={pn.arrow_verts[1][1]}
                stroke="#e11d48" strokeWidth={12} opacity={0.6}
              />
            )}
            {/* P-N text */}
            <g transform={`translate(${pn.x},${pn.y})`}>
              <g transform="scale(1,-1)">
                <text x={0} y={0} fontSize={150} fill="#e11d48" fontWeight={700} textAnchor="middle" opacity={0.8}>
                  {pn.text}
                </text>
              </g>
            </g>
          </g>
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
              <circle cx={s.center[0]} cy={s.center[1]} r={r * 1.8} fill="transparent" stroke="none" />
              {isSelected && (
                <>
                  <circle cx={s.center[0]} cy={s.center[1]} r={r + 200}
                    fill="none" stroke="#ef4444" strokeWidth={25} opacity={0.8}>
                    <animate attributeName="r" from={r + 100} to={r + 400} dur="1s" repeatCount="indefinite" />
                    <animate attributeName="opacity" from="0.8" to="0" dur="1s" repeatCount="indefinite" />
                  </circle>
                  <circle cx={s.center[0]} cy={s.center[1]} r={r + 80}
                    fill="none" stroke="#ef4444" strokeWidth={20} strokeDasharray="60,30" opacity={0.7} />
                </>
              )}
              <circle cx={s.center[0]} cy={s.center[1]} r={r}
                fill={colors.fill} stroke={colors.stroke} strokeWidth={isSelected ? 35 : 20} />
              <circle cx={s.center[0]} cy={s.center[1]} r={35} fill={colors.stroke} />
            </g>
          );
        })}

        {/* Highlight markers from list navigation */}
        {highlightCoords && highlightCoords.length > 0 && highlightCoords.map((c, i) => (
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
      </g>
    </svg>
  );
}
