import { useMemo } from "react";
import type { FloorData, Sleeve, CheckResult } from "../types";

interface Props {
  floorData: FloorData;
  lowerFloorData: FloorData | null;
  results: CheckResult[];
  onSleeveHover: (sleeve: Sleeve | null) => void;
  onSleeveClick: (sleeve: Sleeve | null) => void;
  selectedSleeveId: string | null;
  layers: { grid: boolean; wall: boolean; step: boolean; sleeve: boolean; lowerWall: boolean };
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

export default function DrawingView({
  floorData, lowerFloorData, results, onSleeveHover, onSleeveClick,
  selectedSleeveId, layers, colorMode,
}: Props) {
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

  const viewBox = "-5000 -40000 90000 45000";

  return (
    <svg viewBox={viewBox} style={{ width: "100%", height: "100%", background: "#fdfdfe" }} xmlns="http://www.w3.org/2000/svg">
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
            stroke="#d97706" strokeWidth={20} opacity={0.6} />
        ))}

        {/* Sleeves */}
        {layers.sleeve && floorData.sleeves.map((s) => {
          const colors = getSleeveColors(s);
          const isSelected = s.id === selectedSleeveId;
          const r = Math.max(s.diameter / 2, 200);
          return (
            <g key={s.id} style={{ cursor: "pointer" }}
              onMouseEnter={() => onSleeveHover(s)}
              onClick={() => onSleeveClick(s)}>
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
    </svg>
  );
}
