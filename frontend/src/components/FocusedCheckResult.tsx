import type { CheckResult } from "../types";
import CriterionLink from "./CriterionLink";

interface Props {
  result: CheckResult;
  rule?: string;
  additionalResults: CheckResult[];
  onOpenCriterion: (id: number) => void;
}

export default function FocusedCheckResult({ result, rule, additionalResults, onOpenCriterion }: Props) {
  const palette = result.severity === "OK"
    ? { background: "#f0fdf4", border: "#bbf7d0", color: "#15803d" }
    : result.severity === "NG"
      ? { background: "#fef2f2", border: "#fecaca", color: "#b91c1c" }
      : { background: "#fffbeb", border: "#fde68a", color: "#b45309" };
  const details = [["対象", result.target], ["期待", result.expected], ["検出", result.found], ["対応", result.fix_hint]];

  return <section aria-label="選択したチェック結果" style={{ background: palette.background, borderBottom: `1px solid ${palette.border}` }}>
    <div role="status" aria-label="表示中のチェック項目"
      style={{ padding: "8px 16px", background: "#f8fafc", borderBottom: "1px solid #e5e7eb", color: "#374151", fontSize: 12, fontWeight: 600 }}>
      #{result.check_id} {result.check_name} の結果を表示中
    </div>
    <div style={{ padding: "14px 16px" }}>
    <h2 style={{ fontSize: 15, lineHeight: 1.5, color: palette.color, marginBottom: 10 }}>
      #{result.check_id} {result.check_name}：{result.severity}
    </h2>
    <div style={{ fontSize: 11, fontWeight: 600, color: "#475569", marginBottom: 3 }}>判定理由</div>
    <p style={{ fontSize: 12, lineHeight: 1.7, color: "#1f2937", overflowWrap: "anywhere", marginBottom: 8 }}>{result.message}</p>
    <CriterionLink checkId={result.check_id} rule={result.rule || rule} onOpen={onOpenCriterion} />
    {details.some(([, value]) => value) && <dl style={{ display: "grid", gridTemplateColumns: "32px 1fr", gap: "4px 8px", marginTop: 8, fontSize: 11, lineHeight: 1.6, overflowWrap: "anywhere" }}>
      {details.filter(([, value]) => value).map(([label, value]) => <div key={label} style={{ display: "contents" }}>
        <dt style={{ color: "#64748b" }}>{label}</dt><dd style={{ color: "#374151" }}>{value}</dd>
      </div>)}
    </dl>}
    {additionalResults.length > 0 && <div style={{ marginTop: 10, fontSize: 11, lineHeight: 1.6, color: "#374151" }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>同じ項目のほかの判定</div>
      {additionalResults.map((r, i) => <p key={i} style={{ marginTop: 4 }}>{r.severity}：{r.message}</p>)}
    </div>}
    </div>
  </section>;
}
