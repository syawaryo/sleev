import { useEffect, useState } from "react";
import type { AllEntitiesResponse } from "../api";
import { listFloorData, loadEntities, type DemoFloor } from "../demoData";
import DataExplorer from "./DataExplorer";

interface Props {
  floor: DemoFloor;
  onNavigate: (coords: [number, number], sleeveId?: string) => void;
}
const noOverrides = {};

export default function DemoDataView({ floor, onNavigate }: Props) {
  const [data, setData] = useState<AllEntitiesResponse | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let cancelled = false;
    loadEntities(floor).then((value) => { if (!cancelled) { setData(value); setError(""); } })
      .catch((e: Error) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [floor, retry]);

  return <section aria-label="図面データ" style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", background: "#fff" }}>
    <div style={{ padding: "12px 20px", borderBottom: "1px solid #e5e7eb", fontSize: 12, color: "#374151", lineHeight: 1.6 }}>
      <p>図面から読み取った線・文字・スリーブなどの要素を、種類ごとに確認できます。</p>
      <p style={{ fontSize: 11, color: "#6b7280", marginTop: 3 }}>各行はレイヤーごとの集計です。チェックに使わない要素や分類できなかった要素も「その他の要素」に含まれます。</p>
    </div>
    {error ? <div role="alert" style={{ padding: 20, fontSize: 12 }}>{error}
      <button onClick={() => { setError(""); setRetry((n) => n + 1); }} style={{ marginLeft: 12, padding: "5px 12px", border: "1px solid #d1d5db", borderRadius: 5, background: "#fff", color: "#374151", cursor: "pointer" }}>再読み込み</button>
    </div> : data ? <div style={{ flex: 1, minHeight: 0 }}><DataExplorer floorId={null} floorData={listFloorData(floor)} snapshot={data}
      layerOverrides={noOverrides} onNavigate={(coords, sleeveId) => onNavigate(coords, sleeveId ?? undefined)} /></div>
      : <p role="status" style={{ padding: 20, color: "#9ca3af", fontSize: 12 }}>図面データを読み込み中…</p>}
  </section>;
}
