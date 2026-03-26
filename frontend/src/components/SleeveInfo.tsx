import type { Sleeve, CheckResult } from "../types";

interface Props {
  sleeve: Sleeve | null;
  results: CheckResult[];
}

export default function SleeveInfo({ sleeve, results }: Props) {
  if (!sleeve) {
    return (
      <div style={{ padding: 20, color: "#4b5563", fontSize: 13, textAlign: "center", marginTop: 40 }}>
        スリーブにカーソルを合わせると<br />詳細情報が表示されます
      </div>
    );
  }

  const sleeveResults = results.filter((r) => r.sleeve_id === sleeve.id);
  const ngResults = sleeveResults.filter((r) => r.severity === "NG");
  const warnResults = sleeveResults.filter((r) => r.severity === "WARNING");
  const okResults = sleeveResults.filter((r) => r.severity === "OK");

  const worstSeverity = ngResults.length > 0 ? "NG" : warnResults.length > 0 ? "WARNING" : "OK";
  const borderColor = worstSeverity === "NG" ? "#f87171" : worstSeverity === "WARNING" ? "#fbbf24" : "#34d399";

  return (
    <div style={{ padding: 16, fontSize: 13 }}>
      {/* Header */}
      <div style={{
        padding: "10px 14px", borderRadius: 8, marginBottom: 12,
        background: borderColor + "15", borderLeft: `3px solid ${borderColor}`,
      }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#f9fafb" }}>
          {sleeve.pn_number || sleeve.id}
        </div>
        <div style={{ color: "#9ca3af", fontSize: 11, marginTop: 2 }}>
          {sleeve.discipline} | {sleeve.layer}
        </div>
      </div>

      {/* Properties */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 12px", marginBottom: 16 }}>
        <div>
          <div style={{ color: "#6b7280", fontSize: 10, textTransform: "uppercase" }}>径</div>
          <div style={{ color: "#e5e7eb", fontWeight: 600 }}>{sleeve.diameter}mm</div>
        </div>
        <div>
          <div style={{ color: "#6b7280", fontSize: 10, textTransform: "uppercase" }}>FL</div>
          <div style={{ color: "#e5e7eb", fontWeight: 600 }}>{sleeve.fl_text || "-"}</div>
        </div>
        <div>
          <div style={{ color: "#6b7280", fontSize: 10, textTransform: "uppercase" }}>種別</div>
          <div style={{ color: "#e5e7eb" }}>{sleeve.label_text || "-"}</div>
        </div>
        <div>
          <div style={{ color: "#6b7280", fontSize: 10, textTransform: "uppercase" }}>位置</div>
          <div style={{ color: "#e5e7eb", fontSize: 11 }}>
            ({sleeve.center[0].toFixed(0)}, {sleeve.center[1].toFixed(0)})
          </div>
        </div>
      </div>

      {/* Check results */}
      <div style={{ fontSize: 12 }}>
        <div style={{ color: "#6b7280", fontSize: 10, textTransform: "uppercase", marginBottom: 6 }}>
          チェック結果 ({sleeveResults.length})
        </div>

        {ngResults.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            {ngResults.map((r, i) => (
              <div key={i} style={{
                padding: "6px 10px", marginBottom: 3, borderRadius: 4,
                background: "#991b1b20", borderLeft: "2px solid #f87171",
              }}>
                <span style={{ color: "#f87171", fontWeight: 600 }}>#{r.check_id}</span>
                <span style={{ color: "#fca5a5", marginLeft: 6 }}>{r.check_name}</span>
                <div style={{ color: "#d1d5db", fontSize: 11, marginTop: 2 }}>{r.message}</div>
              </div>
            ))}
          </div>
        )}

        {warnResults.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            {warnResults.map((r, i) => (
              <div key={i} style={{
                padding: "6px 10px", marginBottom: 3, borderRadius: 4,
                background: "#92400e20", borderLeft: "2px solid #fbbf24",
              }}>
                <span style={{ color: "#fbbf24", fontWeight: 600 }}>#{r.check_id}</span>
                <span style={{ color: "#fde68a", marginLeft: 6 }}>{r.check_name}</span>
                <div style={{ color: "#d1d5db", fontSize: 11, marginTop: 2 }}>{r.message}</div>
              </div>
            ))}
          </div>
        )}

        {okResults.length > 0 && (
          <details style={{ color: "#6b7280" }}>
            <summary style={{ cursor: "pointer", fontSize: 11 }}>OK ({okResults.length})</summary>
            <div style={{ marginTop: 4 }}>
              {okResults.map((r, i) => (
                <div key={i} style={{ padding: "2px 0", fontSize: 11, color: "#4b5563" }}>
                  #{r.check_id} {r.check_name}
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
