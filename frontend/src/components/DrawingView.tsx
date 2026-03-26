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
  colorMode: "severity" | "fl";
}

const SEVERITY_COLORS: Record<string, string> = {
  NG: "#f87171",
  WARNING: "#fbbf24",
  OK: "#34d399",
};

// FL value -> color mapping
const FL_COLORS: Record<string, string> = {
  "FL-225": "#60a5fa",
  "FL-175": "#818cf8",
  "FL-750": "#f472b6",
  "FL-765": "#e879f9",
  "FL+40": "#fbbf24",
  "FL+0": "#a3e635",
  "FL-60": "#38bdf8",
};
const FL_DEFAULT_COLOR = "#9ca3af";

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

  const getSleeveColor = (s: Sleeve): string => {
    if (colorMode === "fl") {
      return FL_COLORS[s.fl_text || ""] || FL_DEFAULT_COLOR;
    }
    return SEVERITY_COLORS[severityMap.get(s.id) || "OK"];
  };

  const viewBox = "-5000 -40000 90000 45000";

  return (
    <svg
      viewBox={viewBox}
      style={{ width: "100%", height: "100%", background: "#0f172a" }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <g transform="scale(1,-1)">
        {/* Grid lines */}
        {layers.grid && floorData.grid_lines.map((g, i) =>
          g.direction === "H" ? (
            <line key={`gh${i}`} x1={-5000} y1={g.position} x2={85000} y2={g.position}
              stroke="#1e3a5f" strokeWidth={15} strokeDasharray="300,150" />
          ) : (
            <line key={`gv${i}`} x1={g.position} y1={-5000} x2={g.position} y2={40000}
              stroke="#1e3a5f" strokeWidth={15} strokeDasharray="300,150" />
          )
        )}

        {/* Lower floor walls (for #6 check) */}
        {layers.lowerWall && lowerFloorData?.wall_lines.map((w, i) => (
          <line key={`lw${i}`} x1={w.start[0]} y1={w.start[1]} x2={w.end[0]} y2={w.end[1]}
            stroke="#7c3aed" strokeWidth={40} opacity={0.3} />
        ))}

        {/* Wall lines */}
        {layers.wall && floorData.wall_lines.map((w, i) => (
          <line key={`w${i}`} x1={w.start[0]} y1={w.start[1]} x2={w.end[0]} y2={w.end[1]}
            stroke="#475569" strokeWidth={25} />
        ))}

        {/* Step lines */}
        {layers.step && floorData.step_lines.map((s, i) => (
          <line key={`s${i}`} x1={s.start[0]} y1={s.start[1]} x2={s.end[0]} y2={s.end[1]}
            stroke="#92400e" strokeWidth={18} opacity={0.6} />
        ))}

        {/* Sleeves */}
        {layers.sleeve && floorData.sleeves.map((s) => {
          const color = getSleeveColor(s);
          const isSelected = s.id === selectedSleeveId;
          const r = Math.max(s.diameter / 2, 200);
          return (
            <g key={s.id} style={{ cursor: "pointer" }}
              onMouseEnter={() => onSleeveHover(s)}
              onClick={() => onSleeveClick(s)}>
              {/* Hit area (larger invisible circle for easier hover) */}
              <circle cx={s.center[0]} cy={s.center[1]} r={r * 1.5}
                fill="transparent" stroke="none" />
              {/* Visible circle */}
              <circle cx={s.center[0]} cy={s.center[1]} r={r}
                fill={isSelected ? color + "30" : color + "15"}
                stroke={color}
                strokeWidth={isSelected ? 50 : 25} />
              {/* Center dot */}
              <circle cx={s.center[0]} cy={s.center[1]} r={40}
                fill={color} />
            </g>
          );
        })}
      </g>

      {/* FL legend when in fl mode */}
      {colorMode === "fl" && (
        <g transform="translate(500, 500)">
          <rect x={0} y={0} width={2800} height={Object.keys(FL_COLORS).length * 350 + 400}
            fill="#1e293b" rx={100} opacity={0.9} />
          <text x={200} y={300} fill="#e5e7eb" fontSize={250} fontWeight="bold">FL高さ</text>
          {Object.entries(FL_COLORS).map(([fl, color], i) => (
            <g key={fl} transform={`translate(200, ${450 + i * 350})`}>
              <circle cx={150} cy={100} r={100} fill={color} opacity={0.8} />
              <text x={400} y={150} fill="#e5e7eb" fontSize={200}>{fl}</text>
            </g>
          ))}
        </g>
      )}
    </svg>
  );
}
