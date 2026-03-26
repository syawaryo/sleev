import type { CheckResult } from "../types";

interface Props {
  results: CheckResult[];
  selectedSleeveId: string | null;
  filter: "\u5168\u3066" | "NG" | "WARNING" | "OK";
  onFilterChange: (f: "\u5168\u3066" | "NG" | "WARNING" | "OK") => void;
}

const SEVERITY_STYLE: Record<string, { color: string; bg: string }> = {
  NG: { color: "#f87171", bg: "#991b1b20" },
  WARNING: { color: "#fbbf24", bg: "#92400e20" },
  OK: { color: "#34d399", bg: "#065f4620" },
};

export default function ResultsTable({ results, selectedSleeveId, filter, onFilterChange }: Props) {
  let filtered = results;
  if (filter !== "\u5168\u3066") filtered = results.filter((r) => r.severity === filter);
  if (selectedSleeveId) filtered = filtered.filter((r) => r.sleeve_id === selectedSleeveId);

  const counts = {
    NG: results.filter((r) => r.severity === "NG").length,
    WARNING: results.filter((r) => r.severity === "WARNING").length,
    OK: results.filter((r) => r.severity === "OK").length,
  };

  return (
    <div style={{ fontSize: 12 }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 8, alignItems: "center" }}>
        {(["\u5168\u3066", "NG", "WARNING", "OK"] as const).map((f) => {
          const isActive = filter === f;
          const sev = SEVERITY_STYLE[f];
          return (
            <button key={f} onClick={() => onFilterChange(f)}
              style={{
                padding: "3px 10px", borderRadius: 4, fontSize: 11, cursor: "pointer",
                border: `1px solid ${isActive ? (sev?.color || "#6b7280") : "#374151"}`,
                background: isActive ? (sev?.bg || "#1f293720") : "transparent",
                color: sev?.color || "#9ca3af",
              }}>
              {f} {f !== "\u5168\u3066" ? `(${counts[f as keyof typeof counts]})` : `(${results.length})`}
            </button>
          );
        })}
        {selectedSleeveId && (
          <span style={{ color: "#6b7280", marginLeft: 8 }}>
            {selectedSleeveId} のみ表示中
          </span>
        )}
      </div>

      <div style={{ maxHeight: 220, overflow: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #374151", textAlign: "left", color: "#6b7280", fontSize: 11 }}>
              <th style={{ padding: "4px 8px", width: 30 }}>#</th>
              <th style={{ padding: "4px 8px" }}>チェック名</th>
              <th style={{ padding: "4px 8px", width: 70 }}>結果</th>
              <th style={{ padding: "4px 8px" }}>スリーブ</th>
              <th style={{ padding: "4px 8px" }}>メッセージ</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 300).map((r, i) => {
              const sev = SEVERITY_STYLE[r.severity];
              const isHighlighted = r.sleeve_id === selectedSleeveId;
              return (
                <tr key={i} style={{
                  borderBottom: "1px solid #1f2937",
                  background: isHighlighted ? "#1e3a5f30" : "transparent",
                }}>
                  <td style={{ padding: "3px 8px", color: "#6b7280" }}>{r.check_id}</td>
                  <td style={{ padding: "3px 8px", color: "#d1d5db" }}>{r.check_name}</td>
                  <td style={{ padding: "3px 8px" }}>
                    <span style={{
                      padding: "1px 6px", borderRadius: 3, fontSize: 10, fontWeight: 600,
                      color: sev.color, background: sev.bg,
                    }}>
                      {r.severity}
                    </span>
                  </td>
                  <td style={{ padding: "3px 8px", color: "#9ca3af", fontSize: 11 }}>
                    {r.sleeve_id || "-"}
                  </td>
                  <td style={{ padding: "3px 8px", color: "#9ca3af" }}>{r.message}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
