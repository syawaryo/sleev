import { useMemo } from "react";
import type { FloorData, CheckResult, CheckDef } from "../types";

interface Props {
  floorData: FloorData;
  results: CheckResult[];
  checkDefs?: CheckDef[];
  filter: "all" | "NG" | "WARNING" | "OK";
  onFilterChange: (v: "all" | "NG" | "WARNING" | "OK") => void;
  openChecks: Set<number>;
  onOpenChecksChange: (v: Set<number>) => void;
  onNavigate?: (coords: [number, number], sleeveId?: string, relatedCoords?: [number, number][], result?: CheckResult) => void;
  onOpenDrawing?: () => void;
  onOpenCriterion?: (id: number) => void;
}

const SEV_ORDER = { NG: 0, WARNING: 1, OK: 2 };

export default function ListView({ floorData, results, checkDefs, filter, onFilterChange, openChecks, onOpenChecksChange, onNavigate, onOpenDrawing, onOpenCriterion }: Props) {
  const toggleCheck = (id: number) => {
    const next = new Set(openChecks);
    if (next.has(id)) next.delete(id); else next.add(id);
    onOpenChecksChange(next);
  };

  const checkGroups = useMemo(() => {
    const groups = new Map<number, {
      checkId: number; checkName: string; results: CheckResult[];
      worst: "NG" | "WARNING" | "OK"; ngCount: number; warnCount: number; okCount: number;
    }>();
    for (const def of (checkDefs ?? []).filter((d) => d.enabled)) {
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
  }, [results, checkDefs]);

  const filtered = filter === "all" ? checkGroups : checkGroups.filter(g => g.worst === filter && g.results.length > 0);

  const sleeveMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of floorData.sleeves) m.set(s.id, s.pn_number || s.id);
    return m;
  }, [floorData.sleeves]);

  const getCoords = (r: CheckResult): [number, number] | null => {
    if (r.sleeve_id) { const s = floorData.sleeves.find(s => s.id === r.sleeve_id); if (s) return s.center; }
    if (r.related_coords?.length) return r.related_coords[0] as [number, number];
    return null;
  };

  const showDrawing = (rows: CheckResult[]) => {
    const r = rows.find((row) => getCoords(row));
    if (r) onNavigate?.(getCoords(r)!, r.sleeve_id ?? undefined, r.related_coords, r);
    else if (onOpenDrawing) onOpenDrawing();
    else if (floorData.sleeves[0]) onNavigate?.(floorData.sleeves[0].center, floorData.sleeves[0].id);
  };

  const sevColor = (s: string) => s === "NG" ? "#dc2626" : s === "WARNING" ? "#d97706" : "#16a34a";

  const filterColors: Record<string, { border: string; color: string; bg: string }> = {
    NG: { border: "#fecaca", color: "#dc2626", bg: "#fef2f2" },
    WARNING: { border: "#fde68a", color: "#d97706", bg: "#fffbeb" },
    OK: { border: "#bbf7d0", color: "#16a34a", bg: "#f0fdf4" },
  };

  return (
    <div className="check-list" style={{ background: "#ffffff" }}>
      {floorData.sleeves.length === 0 && <div role="status" style={{ padding: "10px 20px", fontSize: 12, color: "#92400e", background: "#fffbeb" }}>
        読み取れたスリーブは0件です。判定対象がないため、OKとは判定していません。
      </div>}
      <div className="no-print" style={{
        display: "flex", gap: 6, padding: "8px 20px",
        borderBottom: "1px solid #f3f4f6", background: "#fff",
      }}>
        {([["all", "全て"], ["NG", "NG"], ["WARNING", "WARN"], ["OK", "OK"]] as const).map(([val, label]) => {
          const isActive = filter === val;
          const c = filterColors[val];
          return (
            <button key={val} onClick={() => onFilterChange(val)}
              style={{
                padding: "3px 12px", borderRadius: 4, cursor: "pointer", fontSize: 11,
                border: "1px solid",
                borderColor: isActive ? (c?.border || "#d1d5db") : "#e5e7eb",
                background: isActive ? (c?.bg || "#f3f4f6") : "#fff",
                color: c?.color || "#111827",
                fontWeight: isActive ? 500 : 400,
              }}>{label}</button>
          );
        })}
      </div>
      {filtered.map(group => {
        const isOpen = openChecks.has(group.checkId);
        return (
          <div key={group.checkId} data-check-id={group.checkId}>
            <div
              role="button" tabIndex={0} aria-expanded={isOpen} aria-label={`#${group.checkId} ${group.checkName}`}
              onClick={() => toggleCheck(group.checkId)}
              onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggleCheck(group.checkId); } }}
              style={{
                padding: "10px 20px", display: "flex", alignItems: "center", gap: 12,
                cursor: "pointer", borderBottom: "1px solid #e5e7eb", background: "#ffffff",
              }}
            >
              <span style={{ color: "#374151", fontSize: 12 }}>{isOpen ? "▾" : "▸"}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: group.results.length ? sevColor(group.worst) : "#9ca3af" }}>
                #{group.checkId}
              </span>
              <span style={{ fontSize: 13, fontWeight: 500, color: "#111827", flex: 1 }}>
                {group.checkName}
              </span>
              {group.ngCount > 0 && <span style={{ fontSize: 13, fontWeight: 600, color: "#dc2626" }}>{group.ngCount} NG</span>}
              {group.warnCount > 0 && <span style={{ fontSize: 13, fontWeight: 600, color: "#d97706" }}>{group.warnCount} WARN</span>}
              <span style={{ fontSize: 13, color: "#6b7280" }}>{group.results.length ? `${group.okCount} OK` : "未判定・対象なし"}</span>
              {onOpenCriterion && <button aria-label={`#${group.checkId}の基準`} onClick={(e) => { e.stopPropagation(); onOpenCriterion(group.checkId); }}
                style={{ border: "none", background: "none", color: "#6b7280", fontSize: 11, cursor: "pointer", padding: "1px 4px", textDecoration: "underline" }}>基準</button>}
              <button aria-label={`#${group.checkId}の図面を見る`} onClick={(e) => { e.stopPropagation(); showDrawing(group.results); }}
                style={{ border: "1px solid #e5e7eb", borderRadius: 4, background: "#fff", color: "#374151", fontSize: 11, cursor: "pointer", padding: "1px 8px" }}>図面へ</button>
            </div>

            {isOpen && (
              <div style={{ borderBottom: "1px solid #e5e7eb", background: "#ffffff" }}>
                {(() => {
                  const issues = group.results.filter(r => r.severity !== "OK");
                  const nonOk = issues.length ? issues : group.results;
                  const hasSleeveCol = nonOk.some(r => r.sleeve_id);
                  if (nonOk.length === 0) {
                    return <div style={{ padding: "10px 20px", fontSize: 13, color: "#6b7280" }}>判定結果がありません。対象データをご確認ください。</div>;
                  }
                  return (
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <tbody>
                        {nonOk.map((r, i) => {
                          const coords = getCoords(r);
                          const name = r.sleeve_id ? sleeveMap.get(r.sleeve_id) : null;
                          return (
                            <tr
                              key={i}
                              role="button" tabIndex={0}
                              onClick={() => showDrawing([r])}
                              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); showDrawing([r]); } }}
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
                  );
                })()}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
