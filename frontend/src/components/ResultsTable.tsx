import type { CheckResult } from "../types";

interface Props {
  results: CheckResult[];
  selectedSleeveId: string | null;
  filter: "全て" | "NG" | "WARNING" | "OK";
  onFilterChange: (f: "全て" | "NG" | "WARNING" | "OK") => void;
}

export default function ResultsTable({ results, selectedSleeveId, filter, onFilterChange }: Props) {
  let filtered = results;
  if (filter !== "全て") filtered = results.filter(r => r.severity === filter);
  if (selectedSleeveId) filtered = filtered.filter(r => r.sleeve_id === selectedSleeveId);

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        {(["全て", "NG", "WARNING", "OK"] as const).map(f => (
          <button key={f} onClick={() => onFilterChange(f)}
                  style={{
                    padding: "4px 12px", borderRadius: 4, border: "1px solid #444",
                    background: filter === f ? "#333" : "transparent",
                    color: f === "NG" ? "#ef4444" : f === "WARNING" ? "#f59e0b" : f === "OK" ? "#22c55e" : "#fff",
                    cursor: "pointer",
                  }}>
            {f}
          </button>
        ))}
      </div>
      <div style={{ maxHeight: 400, overflow: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #444", textAlign: "left" }}>
              <th style={{padding: 4}}>#</th>
              <th style={{padding: 4}}>チェック名</th>
              <th style={{padding: 4}}>結果</th>
              <th style={{padding: 4}}>スリーブ</th>
              <th style={{padding: 4}}>メッセージ</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 200).map((r, i) => (
              <tr key={i} style={{
                borderBottom: "1px solid #222",
                background: r.sleeve_id === selectedSleeveId ? "#333" : "transparent",
              }}>
                <td style={{padding: 4}}>{r.check_id}</td>
                <td style={{padding: 4}}>{r.check_name}</td>
                <td style={{padding: 4, color: r.severity === "NG" ? "#ef4444" : r.severity === "WARNING" ? "#f59e0b" : "#22c55e"}}>
                  {r.severity}
                </td>
                <td style={{padding: 4, fontSize: 12}}>{r.sleeve_id || "-"}</td>
                <td style={{padding: 4}}>{r.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
