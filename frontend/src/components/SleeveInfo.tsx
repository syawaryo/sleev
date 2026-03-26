import type { Sleeve, CheckResult } from "../types";

interface Props {
  sleeve: Sleeve | null;
  results: CheckResult[];
}

export default function SleeveInfo({ sleeve, results }: Props) {
  if (!sleeve) return <div style={{ padding: 16, color: "#888" }}>スリーブを選択してください</div>;

  const sleeveResults = results.filter(r => r.sleeve_id === sleeve.id);
  const ngResults = sleeveResults.filter(r => r.severity === "NG");
  const warnResults = sleeveResults.filter(r => r.severity === "WARNING");

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ margin: "0 0 8px" }}>{sleeve.pn_number || sleeve.id}</h3>
      <table style={{ width: "100%", fontSize: 14 }}>
        <tbody>
          <tr><td style={{color:"#888"}}>径</td><td>{sleeve.diameter}mm</td></tr>
          <tr><td style={{color:"#888"}}>位置</td><td>({sleeve.center[0].toFixed(0)}, {sleeve.center[1].toFixed(0)})</td></tr>
          <tr><td style={{color:"#888"}}>種別</td><td>{sleeve.label_text || "-"}</td></tr>
          <tr><td style={{color:"#888"}}>FL</td><td>{sleeve.fl_text || "-"}</td></tr>
          <tr><td style={{color:"#888"}}>設備</td><td>{sleeve.discipline}</td></tr>
        </tbody>
      </table>
      {ngResults.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ color: "#ef4444", fontWeight: "bold" }}>NG ({ngResults.length})</div>
          {ngResults.map((r, i) => (
            <div key={i} style={{ fontSize: 13, padding: "2px 0", color: "#ef4444" }}>
              #{r.check_id} {r.check_name}: {r.message}
            </div>
          ))}
        </div>
      )}
      {warnResults.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ color: "#f59e0b", fontWeight: "bold" }}>WARNING ({warnResults.length})</div>
          {warnResults.map((r, i) => (
            <div key={i} style={{ fontSize: 13, padding: "2px 0", color: "#f59e0b" }}>
              #{r.check_id} {r.check_name}: {r.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
