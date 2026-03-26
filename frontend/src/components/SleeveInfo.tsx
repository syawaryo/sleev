import type { Sleeve, CheckResult } from "../types";

interface Props {
  sleeve: Sleeve;
  results: CheckResult[];
}

export default function SleeveInfo({ sleeve, results }: Props) {
  const sleeveResults = results.filter((r) => r.sleeve_id === sleeve.id);
  const ngResults = sleeveResults.filter((r) => r.severity === "NG");
  const warnResults = sleeveResults.filter((r) => r.severity === "WARNING");

  const worst = ngResults.length > 0 ? "NG" : warnResults.length > 0 ? "WARNING" : "OK";
  const badgeStyle: Record<string, { bg: string; color: string }> = {
    NG: { bg: "#fef2f2", color: "#dc2626" },
    WARNING: { bg: "#fffbeb", color: "#d97706" },
    OK: { bg: "#f0fdf4", color: "#16a34a" },
  };
  const badge = badgeStyle[worst];

  return (
    <div style={{
      background: "#fff", border: "1px solid #e5e7eb", borderRadius: 12, width: 280,
      boxShadow: "0 4px 16px rgba(0,0,0,0.06)", overflow: "hidden", fontSize: 12,
    }}>
      {/* Header */}
      <div style={{ padding: "10px 14px", borderBottom: "1px solid #f3f4f6", display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ background: badge.bg, color: badge.color, padding: "1px 6px", borderRadius: 3, fontSize: 9, fontWeight: 600 }}>{worst}</span>
        <span style={{ fontWeight: 700, color: "#111827", fontSize: 14 }}>{sleeve.pn_number || sleeve.id}</span>
        <span style={{ marginLeft: "auto", color: "#9ca3af", fontSize: 10 }}>{sleeve.discipline}</span>
      </div>

      {/* Properties */}
      <div style={{ padding: "8px 14px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        <div><div style={{ color: "#9ca3af", fontSize: 9 }}>径</div><div style={{ color: "#111827", fontWeight: 600 }}>{sleeve.diameter}mm</div></div>
        <div><div style={{ color: "#9ca3af", fontSize: 9 }}>FL</div><div style={{ color: "#111827", fontWeight: 600 }}>{sleeve.fl_text || "-"}</div></div>
        <div><div style={{ color: "#9ca3af", fontSize: 9 }}>種別</div><div style={{ color: "#374151" }}>{sleeve.label_text || "-"}</div></div>
        <div><div style={{ color: "#9ca3af", fontSize: 9 }}>座標</div><div style={{ color: "#374151", fontSize: 11 }}>({sleeve.center[0].toFixed(0)}, {sleeve.center[1].toFixed(0)})</div></div>
      </div>

      {/* Issues */}
      {(ngResults.length > 0 || warnResults.length > 0) && (
        <div style={{ padding: "6px 14px 10px", borderTop: "1px solid #f3f4f6" }}>
          {ngResults.map((r, i) => (
            <div key={`ng${i}`} style={{ background: "#fef2f2", borderLeft: "2px solid #ef4444", padding: "5px 8px", borderRadius: "0 4px 4px 0", marginBottom: 3, fontSize: 10 }}>
              <span style={{ color: "#dc2626", fontWeight: 600 }}>#{r.check_id}</span>{" "}
              <span style={{ color: "#7f1d1d" }}>{r.check_name}</span>
              <div style={{ color: "#6b7280", marginTop: 1 }}>{r.message}</div>
            </div>
          ))}
          {warnResults.map((r, i) => (
            <div key={`w${i}`} style={{ background: "#fffbeb", borderLeft: "2px solid #fbbf24", padding: "5px 8px", borderRadius: "0 4px 4px 0", marginBottom: 3, fontSize: 10 }}>
              <span style={{ color: "#d97706", fontWeight: 600 }}>#{r.check_id}</span>{" "}
              <span style={{ color: "#92400e" }}>{r.check_name}</span>
              <div style={{ color: "#6b7280", marginTop: 1 }}>{r.message}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
