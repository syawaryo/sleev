import { useMemo } from "react";
import type { FloorData, CheckResult } from "../types";

interface Props {
  floorData: FloorData;
  results: CheckResult[];
  filter: "all" | "NG" | "WARNING" | "OK";
}

interface SleeveRow {
  id: string;
  pn: string;
  diameter: number;
  fl: string;
  discipline: string;
  label: string;
  worst: "NG" | "WARNING" | "OK";
  ngItems: string[];
  warnItems: string[];
}

const BADGE: Record<string, { bg: string; color: string; border: string }> = {
  NG: { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
  WARNING: { bg: "#fffbeb", color: "#d97706", border: "#fde68a" },
  OK: { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" },
};

const ROW_BG: Record<string, string> = {
  NG: "#fef2f2",
  WARNING: "#fffbeb",
  OK: "transparent",
};

export default function ListView({ floorData, results, filter }: Props) {
  const rows = useMemo(() => {
    const map = new Map<string, SleeveRow>();
    for (const s of floorData.sleeves) {
      map.set(s.id, {
        id: s.id,
        pn: s.pn_number || "-",
        diameter: s.diameter,
        fl: s.fl_text || "-",
        discipline: s.discipline,
        label: s.label_text || "-",
        worst: "OK",
        ngItems: [],
        warnItems: [],
      });
    }
    for (const r of results) {
      if (!r.sleeve_id) continue;
      const row = map.get(r.sleeve_id);
      if (!row) continue;
      if (r.severity === "NG") {
        row.ngItems.push(`#${r.check_id} ${r.message}`);
        row.worst = "NG";
      } else if (r.severity === "WARNING") {
        row.warnItems.push(`#${r.check_id} ${r.message}`);
        if (row.worst !== "NG") row.worst = "WARNING";
      }
    }
    const arr = Array.from(map.values());
    // Sort: NG first, then WARNING, then OK
    arr.sort((a, b) => {
      const order = { NG: 0, WARNING: 1, OK: 2 };
      return order[a.worst] - order[b.worst];
    });
    return arr;
  }, [floorData, results]);

  const filtered = filter === "all" ? rows : rows.filter((r) => r.worst === filter);

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
      <thead>
        <tr style={{ background: "#f9fafb", borderBottom: "1px solid #e5e7eb", color: "#6b7280", fontSize: 10, textAlign: "left" }}>
          <th style={{ padding: "8px 16px" }}>スリーブ</th>
          <th style={{ padding: "8px" }}>径</th>
          <th style={{ padding: "8px" }}>FL</th>
          <th style={{ padding: "8px" }}>種別</th>
          <th style={{ padding: "8px" }}>設備</th>
          <th style={{ padding: "8px", width: 60 }}>判定</th>
          <th style={{ padding: "8px" }}>指摘事項</th>
        </tr>
      </thead>
      <tbody>
        {filtered.map((row) => {
          const badge = BADGE[row.worst];
          const issues = [...row.ngItems, ...row.warnItems];
          return (
            <tr key={row.id} style={{ borderBottom: "1px solid #f3f4f6", background: ROW_BG[row.worst] }}>
              <td style={{ padding: "8px 16px", fontWeight: 600, color: "#111827" }}>{row.pn}</td>
              <td style={{ padding: 8, color: "#374151" }}>{row.diameter}mm</td>
              <td style={{ padding: 8, color: "#374151" }}>{row.fl}</td>
              <td style={{ padding: 8, color: "#374151", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.label}</td>
              <td style={{ padding: 8, color: "#374151" }}>{row.discipline}</td>
              <td style={{ padding: 8 }}>
                <span style={{
                  background: badge.bg, color: badge.color, border: `1px solid ${badge.border}`,
                  padding: "1px 6px", borderRadius: 3, fontSize: 10, fontWeight: 600,
                }}>{row.worst}</span>
              </td>
              <td style={{ padding: 8, fontSize: 10 }}>
                {issues.length > 0 ? (
                  <span style={{ color: row.worst === "NG" ? "#dc2626" : "#d97706" }}>
                    {issues.join(", ")}
                  </span>
                ) : (
                  <span style={{ color: "#9ca3af" }}>-</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
