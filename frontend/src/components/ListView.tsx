import { useMemo, useState } from "react";
import type { FloorData, CheckResult } from "../types";

interface Props {
  floorData: FloorData;
  results: CheckResult[];
  filter: "all" | "NG" | "WARNING" | "OK";
  onNavigate?: (coords: [number, number], sleeveId?: string, relatedCoords?: [number, number][]) => void;
}

const CHECK_DEFS: { id: number; name: string }[] = [
  { id: 2, name: "スリーブ用途・設備種別" },
  { id: 3, name: "呼び口径・外径記載" },
  { id: 4, name: "通り芯寸法合計" },
  { id: 5, name: "勾配確保" },
  { id: 6, name: "下階壁干渉" },
  { id: 7, name: "段差スラブ近接" },
  { id: 8, name: "基準レベル記載" },
  { id: 9, name: "両側寸法" },
  { id: 10, name: "段差基準寸法" },
  { id: 11, name: "スリーブ芯寸法" },
  { id: 12, name: "柱面・仕上面寸法" },
  { id: 13, name: "寸法表記統一" },
  { id: 14, name: "スリーブNo記載" },
];

const SEV_ORDER = { NG: 0, WARNING: 1, OK: 2 };

export default function ListView({ floorData, results, filter, onNavigate }: Props) {
  const [openChecks, setOpenChecks] = useState<Set<number>>(new Set());

  const toggleCheck = (id: number) => {
    setOpenChecks(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const checkGroups = useMemo(() => {
    const groups = new Map<number, {
      checkId: number; checkName: string; results: CheckResult[];
      worst: "NG" | "WARNING" | "OK"; ngCount: number; warnCount: number; okCount: number;
    }>();
    for (const def of CHECK_DEFS) {
      groups.set(def.id, { checkId: def.id, checkName: def.name, results: [], worst: "OK", ngCount: 0, warnCount: 0, okCount: 0 });
    }
    for (const r of results) {
      let g = groups.get(r.check_id);
      if (!g) { g = { checkId: r.check_id, checkName: r.check_name, results: [], worst: "OK", ngCount: 0, warnCount: 0, okCount: 0 }; groups.set(r.check_id, g); }
      g.results.push(r);
      if (r.severity === "NG") { g.ngCount++; g.worst = "NG"; }
      else if (r.severity === "WARNING") { g.warnCount++; if (g.worst !== "NG") g.worst = "WARNING"; }
      else g.okCount++;
    }
    for (const g of groups.values()) g.results.sort((a, b) => SEV_ORDER[a.severity as keyof typeof SEV_ORDER] - SEV_ORDER[b.severity as keyof typeof SEV_ORDER]);
    return Array.from(groups.values()).sort((a, b) => SEV_ORDER[a.worst] - SEV_ORDER[b.worst]);
  }, [results]);

  const filtered = filter === "all" ? checkGroups : checkGroups.filter(g => g.worst === filter);

  const sleeveMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of floorData.sleeves) m.set(s.id, s.pn_number || s.id);
    return m;
  }, [floorData.sleeves]);

  const getCoords = (r: CheckResult): [number, number] | null => {
    if (r.related_coords?.length) return r.related_coords[0] as [number, number];
    if (r.sleeve_id) { const s = floorData.sleeves.find(s => s.id === r.sleeve_id); if (s) return s.center; }
    return null;
  };

  const sevColor = (s: string) => s === "NG" ? "#dc2626" : s === "WARNING" ? "#d97706" : "#16a34a";

  return (
    <div style={{ background: "#ffffff" }}>
      {filtered.map(group => {
        const isOpen = openChecks.has(group.checkId);
        const nonOk = group.results.filter(r => r.severity !== "OK");
        const hasSleeveCol = nonOk.some(r => r.sleeve_id);

        return (
          <div key={group.checkId}>
            <div
              onClick={() => toggleCheck(group.checkId)}
              style={{
                padding: "10px 20px", display: "flex", alignItems: "center", gap: 12,
                cursor: "pointer", borderBottom: "1px solid #e5e7eb", background: "#ffffff",
              }}
            >
              <span style={{ color: "#374151", fontSize: 12 }}>{isOpen ? "▾" : "▸"}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: sevColor(group.worst) }}>
                #{group.checkId}
              </span>
              <span style={{ fontSize: 13, fontWeight: 500, color: "#111827", flex: 1 }}>
                {group.checkName}
              </span>
              {group.ngCount > 0 && <span style={{ fontSize: 13, fontWeight: 600, color: "#dc2626" }}>{group.ngCount} NG</span>}
              {group.warnCount > 0 && <span style={{ fontSize: 13, fontWeight: 600, color: "#d97706" }}>{group.warnCount} WARN</span>}
              <span style={{ fontSize: 13, color: "#6b7280" }}>{group.okCount} OK</span>
            </div>

            {isOpen && (
              <div style={{ borderBottom: "1px solid #e5e7eb", background: "#ffffff" }}>
                {nonOk.length === 0 ? (
                  <div style={{ padding: "10px 20px", fontSize: 13, color: "#6b7280" }}>全て OK</div>
                ) : (
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <tbody>
                      {nonOk.map((r, i) => {
                        const coords = getCoords(r);
                        const name = r.sleeve_id ? sleeveMap.get(r.sleeve_id) : null;
                        return (
                          <tr
                            key={i}
                            onClick={() => coords && onNavigate?.(coords, r.sleeve_id ?? undefined, (r.related_coords as [number, number][]) || [])}
                            style={{ borderBottom: "1px solid #e5e7eb", cursor: coords ? "pointer" : "default" }}
                          >
                            {hasSleeveCol && (
                              <td style={{ padding: "8px 12px 8px 32px", width: 300, fontSize: 13, fontWeight: 500, color: "#111827" }}>
                                {name || "-"}
                              </td>
                            )}
                            <td style={{ padding: "8px 12px" + (!hasSleeveCol ? " 8px 32px" : ""), fontSize: 13, color: "#111827" }}>
                              {r.message}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
