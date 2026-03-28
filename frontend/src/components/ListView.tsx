import { useMemo, useState } from "react";
import type { FloorData, CheckResult } from "../types";

interface Props {
  floorData: FloorData;
  results: CheckResult[];
  filter: "all" | "NG" | "WARNING" | "OK";
  onNavigate?: (coords: [number, number], sleeveId?: string, relatedCoords?: [number, number][]) => void;
}

// Check definitions with display names
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

const SEVERITY_ORDER = { NG: 0, WARNING: 1, OK: 2 };

const BADGE: Record<string, { bg: string; color: string; border: string }> = {
  NG: { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" },
  WARNING: { bg: "#fffbeb", color: "#d97706", border: "#fde68a" },
  OK: { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" },
};

function Badge({ severity }: { severity: string }) {
  const b = BADGE[severity] || BADGE.OK;
  return (
    <span style={{
      background: b.bg, color: b.color, border: `1px solid ${b.border}`,
      padding: "1px 6px", borderRadius: 3, fontSize: 10, fontWeight: 600,
    }}>{severity}</span>
  );
}

export default function ListView({ floorData, results, filter, onNavigate }: Props) {
  const [openChecks, setOpenChecks] = useState<Set<number>>(new Set());

  const toggleCheck = (id: number) => {
    setOpenChecks(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Group results by check_id
  const checkGroups = useMemo(() => {
    const groups = new Map<number, {
      checkId: number;
      checkName: string;
      results: CheckResult[];
      worst: "NG" | "WARNING" | "OK";
      ngCount: number;
      warnCount: number;
      okCount: number;
    }>();

    for (const def of CHECK_DEFS) {
      groups.set(def.id, {
        checkId: def.id,
        checkName: def.name,
        results: [],
        worst: "OK",
        ngCount: 0,
        warnCount: 0,
        okCount: 0,
      });
    }

    for (const r of results) {
      let group = groups.get(r.check_id);
      if (!group) {
        group = {
          checkId: r.check_id,
          checkName: r.check_name,
          results: [],
          worst: "OK",
          ngCount: 0,
          warnCount: 0,
          okCount: 0,
        };
        groups.set(r.check_id, group);
      }
      group.results.push(r);
      if (r.severity === "NG") {
        group.ngCount++;
        group.worst = "NG";
      } else if (r.severity === "WARNING") {
        group.warnCount++;
        if (group.worst !== "NG") group.worst = "WARNING";
      } else {
        group.okCount++;
      }
    }

    // Sort results within each group: NG first
    for (const group of groups.values()) {
      group.results.sort((a, b) =>
        SEVERITY_ORDER[a.severity as keyof typeof SEVERITY_ORDER] -
        SEVERITY_ORDER[b.severity as keyof typeof SEVERITY_ORDER]
      );
    }

    return Array.from(groups.values()).sort((a, b) =>
      SEVERITY_ORDER[a.worst] - SEVERITY_ORDER[b.worst]
    );
  }, [results]);

  const filtered = filter === "all"
    ? checkGroups
    : checkGroups.filter(g => g.worst === filter);

  // Find sleeve name for a result
  const sleeveMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of floorData.sleeves) {
      map.set(s.id, s.pn_number || s.id);
    }
    return map;
  }, [floorData.sleeves]);

  // Find coordinates for navigation
  const getCoords = (r: CheckResult): [number, number] | null => {
    if (r.related_coords && r.related_coords.length > 0) {
      return r.related_coords[0] as [number, number];
    }
    if (r.sleeve_id) {
      const s = floorData.sleeves.find(s => s.id === r.sleeve_id);
      if (s) return s.center;
    }
    return null;
  };

  return (
    <div style={{ padding: "0 0 20px 0" }}>
      {filtered.map(group => {
        const isOpen = openChecks.has(group.checkId);
        const nonOkResults = group.results.filter(r => r.severity !== "OK");
        const displayResults = isOpen ? nonOkResults : [];

        return (
          <div key={group.checkId} style={{ borderBottom: "1px solid #e5e7eb" }}>
            {/* Check header — toggle */}
            <div
              onClick={() => toggleCheck(group.checkId)}
              style={{
                padding: "10px 16px",
                display: "flex",
                alignItems: "center",
                gap: 10,
                cursor: "pointer",
                background: isOpen ? "#f9fafb" : "transparent",
                userSelect: "none",
              }}
            >
              <span style={{ color: "#9ca3af", fontSize: 11, width: 16 }}>
                {isOpen ? "▾" : "▸"}
              </span>
              <span style={{ fontWeight: 600, fontSize: 12, color: "#111827", flex: 1 }}>
                #{group.checkId} {group.checkName}
              </span>
              <Badge severity={group.worst} />
              <div style={{ display: "flex", gap: 4, fontSize: 10 }}>
                {group.ngCount > 0 && (
                  <span style={{ color: "#dc2626" }}>{group.ngCount} NG</span>
                )}
                {group.warnCount > 0 && (
                  <span style={{ color: "#d97706" }}>{group.warnCount} WARN</span>
                )}
                <span style={{ color: "#9ca3af" }}>{group.okCount} OK</span>
              </div>
            </div>

            {/* Expanded results */}
            {isOpen && (
              <div style={{ padding: "0 16px 10px 42px" }}>
                {nonOkResults.length === 0 ? (
                  <div style={{ color: "#9ca3af", fontSize: 11, padding: "4px 0" }}>
                    全て OK
                  </div>
                ) : (
                  nonOkResults.map((r, i) => {
                    const coords = getCoords(r);
                    const sleeveName = r.sleeve_id ? sleeveMap.get(r.sleeve_id) : null;
                    return (
                      <div
                        key={i}
                        onClick={() => coords && onNavigate?.(
                          coords,
                          r.sleeve_id ?? undefined,
                          (r.related_coords as [number, number][]) || [],
                        )}
                        style={{
                          padding: "6px 10px",
                          marginBottom: 3,
                          borderRadius: 4,
                          background: r.severity === "NG" ? "#fef2f2" : "#fffbeb",
                          borderLeft: `3px solid ${r.severity === "NG" ? "#ef4444" : "#fbbf24"}`,
                          cursor: coords ? "pointer" : "default",
                          fontSize: 11,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <Badge severity={r.severity} />
                          {sleeveName && (
                            <span style={{ fontWeight: 600, color: "#374151" }}>{sleeveName}</span>
                          )}
                        </div>
                        <div style={{ color: "#6b7280", marginTop: 3, fontSize: 11 }}>
                          {r.message}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
