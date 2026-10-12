interface Props {
  checkId: number;
  rule?: string;
  onOpen: (id: number) => void;
}

export default function CriterionLink({ checkId, rule, onOpen }: Props) {
  return <button type="button" className="criterion-link" onClick={() => onOpen(checkId)}
    aria-label={`チェック観点 #${checkId}を見る`}
    style={{ display: "block", width: "100%", gridColumn: "1 / -1", margin: "4px 0", padding: "9px 10px", border: "1px solid #cbd5e1", borderRadius: 5, background: "#f8fafc", color: "#374151", textAlign: "left", fontFamily: "inherit", cursor: "pointer" }}>
    <span style={{ display: "block", fontSize: 10, fontWeight: 600, color: "#6b7280", marginBottom: rule ? 4 : 0 }}>基準</span>
    {rule && <span style={{ display: "block", fontSize: 11, lineHeight: 1.6 }}>{rule}</span>}
    <span style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginTop: 7, fontSize: 11, fontWeight: 600, color: "#334155" }}>
      <span style={{ textDecoration: "underline", textUnderlineOffset: 2 }}>チェック観点 #{checkId}を見る</span><span aria-hidden="true" style={{ fontSize: 16 }}>→</span>
    </span>
  </button>;
}
