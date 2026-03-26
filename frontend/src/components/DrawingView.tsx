import type { FloorData, Sleeve, CheckResult } from "../types";

interface Props {
  floorData: FloorData;
  results: CheckResult[];
  onSleeveHover: (sleeve: Sleeve | null) => void;
  onSleeveClick: (sleeve: Sleeve | null) => void;
  selectedSleeveId: string | null;
}

// The drawing is in mm coordinates. We need to transform to screen coordinates.
// Building range: X=0~80000, Y=0~34000
// SVG viewBox handles the coordinate transform.

export default function DrawingView({ floorData, results, onSleeveHover, onSleeveClick, selectedSleeveId }: Props) {
  // Build severity map: sleeve_id -> worst severity
  const severityMap = new Map<string, "NG" | "WARNING" | "OK">();
  for (const r of results) {
    if (r.sleeve_id) {
      const current = severityMap.get(r.sleeve_id);
      if (!current || r.severity === "NG" || (r.severity === "WARNING" && current === "OK")) {
        severityMap.set(r.sleeve_id, r.severity);
      }
    }
  }

  const severityColor = (s: string) => {
    if (s === "NG") return "#ef4444";
    if (s === "WARNING") return "#f59e0b";
    return "#22c55e";
  };

  // SVG viewBox: flip Y axis (DXF Y goes up, SVG Y goes down)
  // Use transform="scale(1,-1)" on a group and set viewBox accordingly
  const viewBox = "-5000 -40000 90000 45000";

  return (
    <svg
      viewBox={viewBox}
      style={{ width: "100%", height: "70vh", background: "#1a1a2e", border: "1px solid #333" }}
      xmlns="http://www.w3.org/2000/svg"
    >
      <g transform="scale(1,-1)">
        {/* Grid lines */}
        {floorData.grid_lines.map((g, i) => (
          g.direction === "H" ? (
            <line key={`gh${i}`} x1={-5000} y1={g.position} x2={85000} y2={g.position}
                  stroke="#444" strokeWidth={20} strokeDasharray="200,100" />
          ) : (
            <line key={`gv${i}`} x1={g.position} y1={-5000} x2={g.position} y2={40000}
                  stroke="#444" strokeWidth={20} strokeDasharray="200,100" />
          )
        ))}

        {/* Wall lines */}
        {floorData.wall_lines.map((w, i) => (
          <line key={`w${i}`} x1={w.start[0]} y1={w.start[1]} x2={w.end[0]} y2={w.end[1]}
                stroke="#666" strokeWidth={30} />
        ))}

        {/* Step lines */}
        {floorData.step_lines.map((s, i) => (
          <line key={`s${i}`} x1={s.start[0]} y1={s.start[1]} x2={s.end[0]} y2={s.end[1]}
                stroke="#8B4513" strokeWidth={20} />
        ))}

        {/* Sleeves */}
        {floorData.sleeves.map((s) => {
          const severity = severityMap.get(s.id) || "OK";
          const isSelected = s.id === selectedSleeveId;
          return (
            <circle
              key={s.id}
              cx={s.center[0]}
              cy={s.center[1]}
              r={Math.max(s.diameter / 2, 150)}
              fill={isSelected ? severityColor(severity) + "40" : "none"}
              stroke={severityColor(severity)}
              strokeWidth={isSelected ? 60 : 30}
              style={{ cursor: "pointer" }}
              onMouseEnter={() => onSleeveHover(s)}
              onMouseLeave={() => onSleeveHover(null)}
              onClick={() => onSleeveClick(s)}
            />
          );
        })}
      </g>
    </svg>
  );
}
