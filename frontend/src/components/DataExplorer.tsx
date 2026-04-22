import { useMemo, useState } from "react";
import type { FloorData } from "../types";

interface Props {
  floorData: FloorData;
  onNavigate: (coords: [number, number], sleeveId?: string | null) => void;
}

type EntityType =
  | "sleeve"
  | "wall"
  | "grid"
  | "dim"
  | "step"
  | "column"
  | "slab_outline"
  | "slab_label"
  | "slab_zone"
  | "pn_label";

interface EntityRow {
  id: string;
  type: EntityType;
  typeLabel: string;
  rawLayer: string;           // 元のDXFレイヤー名 / IFCクラス名（空文字なら無し）
  groupName: string;           // 正規化後のカテゴリ名
  label: string;
  properties: string;
  navigate: [number, number];
  sleeveId?: string;
}

const TYPE_LABELS: Record<EntityType, string> = {
  sleeve: "スリーブ",
  wall: "壁",
  grid: "通り芯",
  dim: "寸法",
  step: "段差",
  column: "柱/仕上",
  slab_outline: "スラブ線",
  slab_label: "スラブラベル",
  slab_zone: "FLゾーン",
  pn_label: "P-Nラベル",
};

// Desired display order for normalized group names.
const GROUP_ORDER = [
  "衛生スリーブ",
  "空調スリーブ",
  "電気スリーブ",
  "その他スリーブ",
  "用途不明スリーブ",
  "外壁",
  "内壁",
  "通り芯",
  "柱・仕上線",
  "スラブ外形",
  "スラブ情報",
  "段差線",
  "寸法線",
  "FL表記",
  "P-N番号",
  "不明",
];

function groupOrderIdx(name: string): number {
  const i = GROUP_ORDER.indexOf(name);
  return i < 0 ? GROUP_ORDER.length + 1 : i;
}

// ---------------------------------------------------------------------------
// Normalization — map entity + raw layer → human-readable group name.
// ---------------------------------------------------------------------------

function normalizeSleeveGroup(discipline: string, rawLayer: string): string {
  if (discipline === "衛生") return "衛生スリーブ";
  if (discipline === "空調") return "空調スリーブ";
  if (discipline === "電気") return "電気スリーブ";
  // Fallback: match against raw layer name
  if (/衛生|san/i.test(rawLayer)) return "衛生スリーブ";
  if (/空調|ac|hvac/i.test(rawLayer)) return "空調スリーブ";
  if (/電気|ele|cable/i.test(rawLayer)) return "電気スリーブ";
  if (discipline && discipline !== "") return "その他スリーブ";
  return "用途不明スリーブ";
}

function normalizeWallGroup(wallType: string, rawLayer: string): string {
  if (wallType === "外壁") return "外壁";
  if (/外壁|ext/i.test(rawLayer)) return "外壁";
  return "内壁";
}

function collectRows(fd: FloorData): EntityRow[] {
  const rows: EntityRow[] = [];

  fd.sleeves.forEach((s) => {
    const size = s.shape === "rect"
      ? `□${s.width ?? "?"}×${s.height ?? "?"}`
      : `ø${s.diameter}`;
    const props = [
      size,
      s.fl_text,
      s.discipline,
      s.pn_number ? `P-N${s.pn_number}` : null,
      s.label_text,
    ].filter(Boolean).join("  ");
    rows.push({
      id: `sleeve-${s.id}`,
      type: "sleeve",
      typeLabel: TYPE_LABELS.sleeve,
      rawLayer: s.layer || "",
      groupName: normalizeSleeveGroup(s.discipline, s.layer || ""),
      label: s.id,
      properties: props,
      navigate: s.center,
      sleeveId: s.id,
    });
  });

  fd.wall_lines.forEach((w, i) => {
    const len = Math.round(Math.hypot(w.end[0] - w.start[0], w.end[1] - w.start[1]));
    const kind = w.wall_type || "壁";
    rows.push({
      id: `wall-${i}`,
      type: "wall",
      typeLabel: TYPE_LABELS.wall,
      rawLayer: w.layer || "",
      groupName: normalizeWallGroup(w.wall_type, w.layer || ""),
      label: kind,
      properties: `長さ ${len}`,
      navigate: [(w.start[0] + w.end[0]) / 2, (w.start[1] + w.end[1]) / 2],
    });
  });

  fd.grid_lines.forEach((g, i) => {
    rows.push({
      id: `grid-${i}`,
      type: "grid",
      typeLabel: TYPE_LABELS.grid,
      rawLayer: "",
      groupName: "通り芯",
      label: g.axis_label,
      properties: g.direction === "H" ? "水平" : "垂直",
      navigate: g.direction === "H" ? [0, g.position] : [g.position, 0],
    });
  });

  fd.dim_lines.forEach((d, i) => {
    const val = Math.round(d.measurement);
    if (val < 1) return;
    rows.push({
      id: `dim-${i}`,
      type: "dim",
      typeLabel: TYPE_LABELS.dim,
      rawLayer: d.layer || "",
      groupName: "寸法線",
      label: `${val}`,
      properties: d.text_override || "",
      navigate: d.defpoint1,
    });
  });

  fd.step_lines.forEach((s, i) => {
    rows.push({
      id: `step-${i}`,
      type: "step",
      typeLabel: TYPE_LABELS.step,
      rawLayer: s.layer || "",
      groupName: "段差線",
      label: "段差線",
      properties: "",
      navigate: [(s.start[0] + s.end[0]) / 2, (s.start[1] + s.end[1]) / 2],
    });
  });

  fd.column_lines.forEach((c, i) => {
    rows.push({
      id: `column-${i}`,
      type: "column",
      typeLabel: TYPE_LABELS.column,
      rawLayer: c.layer || "",
      groupName: "柱・仕上線",
      label: "柱/仕上線",
      properties: "",
      navigate: [(c.start[0] + c.end[0]) / 2, (c.start[1] + c.end[1]) / 2],
    });
  });

  (fd.slab_outlines || []).forEach((s, i) => {
    rows.push({
      id: `slabout-${i}`,
      type: "slab_outline",
      typeLabel: TYPE_LABELS.slab_outline,
      rawLayer: "",
      groupName: "スラブ外形",
      label: "スラブ線",
      properties: "",
      navigate: [(s.start[0] + s.end[0]) / 2, (s.start[1] + s.end[1]) / 2],
    });
  });

  (fd.slab_labels || []).forEach((sl, i) => {
    rows.push({
      id: `slablab-${i}`,
      type: "slab_label",
      typeLabel: TYPE_LABELS.slab_label,
      rawLayer: "",
      groupName: "スラブ情報",
      label: sl.slab_no,
      properties: `FL${sl.level}  t=${sl.thickness}`,
      navigate: [sl.x, sl.y],
    });
  });

  (fd.slab_zones || []).forEach((z, i) => {
    rows.push({
      id: `slabzone-${i}`,
      type: "slab_zone",
      typeLabel: TYPE_LABELS.slab_zone,
      rawLayer: "",
      groupName: "FL表記",
      label: z.fl_text,
      properties: `FL${z.fl_value >= 0 ? "+" : ""}${z.fl_value}`,
      navigate: [z.x, z.y],
    });
  });

  (fd.pn_labels || []).forEach((p, i) => {
    rows.push({
      id: `pn-${i}`,
      type: "pn_label",
      typeLabel: TYPE_LABELS.pn_label,
      rawLayer: "",
      groupName: "P-N番号",
      label: p.text,
      properties: `#${p.number}`,
      navigate: [p.x, p.y],
    });
  });

  return rows;
}

export default function DataExplorer({ floorData, onNavigate }: Props) {
  const rows = useMemo(() => collectRows(floorData), [floorData]);
  const [typeFilter, setTypeFilter] = useState<EntityType | "all">("all");
  const [query, setQuery] = useState("");
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter(r => {
      if (typeFilter !== "all" && r.type !== typeFilter) return false;
      if (!q) return true;
      return (
        r.label.toLowerCase().includes(q) ||
        r.rawLayer.toLowerCase().includes(q) ||
        r.groupName.toLowerCase().includes(q) ||
        r.properties.toLowerCase().includes(q) ||
        r.typeLabel.toLowerCase().includes(q)
      );
    });
  }, [rows, typeFilter, query]);

  // Group by normalized name; track distinct raw layers per group.
  const grouped = useMemo(() => {
    type G = { name: string; rawLayers: string[]; entities: EntityRow[] };
    const m = new Map<string, G>();
    for (const r of filtered) {
      let g = m.get(r.groupName);
      if (!g) {
        g = { name: r.groupName, rawLayers: [], entities: [] };
        m.set(r.groupName, g);
      }
      g.entities.push(r);
      if (r.rawLayer && !g.rawLayers.includes(r.rawLayer)) {
        g.rawLayers.push(r.rawLayer);
      }
    }
    return [...m.values()].sort((a, b) => {
      const d = groupOrderIdx(a.name) - groupOrderIdx(b.name);
      if (d !== 0) return d;
      return a.name.localeCompare(b.name, "ja");
    });
  }, [filtered]);

  const autoExpand = query.trim().length > 0 || typeFilter !== "all";

  const toggleGroup = (name: string) => {
    setOpenGroups(p => {
      const next = new Set(p);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  return (
    <div style={{
      padding: "24px 28px 0",
      background: "#fff",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      fontSize: 13,
      color: "#111827",
    }}>
      {/* Filter bar */}
      <div style={{ display: "flex", gap: 10, marginBottom: 18, alignItems: "center" }}>
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value as EntityType | "all")}
          style={{
            padding: "7px 28px 7px 12px",
            fontSize: 12,
            border: "none",
            borderRadius: 6,
            background: "#f5f5f7",
            color: "#374151",
            cursor: "pointer",
            outline: "none",
            appearance: "none",
            backgroundImage:
              "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path d='M1 1l4 4 4-4' stroke='%239ca3af' fill='none' stroke-width='1.2'/></svg>\")",
            backgroundRepeat: "no-repeat",
            backgroundPosition: "right 10px center",
          }}
        >
          <option value="all">全タイプ</option>
          {(Object.entries(TYPE_LABELS) as [EntityType, string][]).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="検索"
          style={{
            flex: 1,
            padding: "7px 14px",
            fontSize: 13,
            border: "none",
            borderRadius: 6,
            background: "#f5f5f7",
            outline: "none",
            color: "#111827",
          }}
        />
      </div>

      {/* Tree */}
      <div style={{ flex: 1, overflow: "auto", marginLeft: -4 }}>
        {grouped.length === 0 ? (
          <div style={{ color: "#9ca3af", textAlign: "center", marginTop: 60, fontSize: 13 }}>
            該当するデータがありません
          </div>
        ) : grouped.map((g, gi) => {
          const isOpen = openGroups.has(g.name) || autoExpand;
          return (
            <div key={g.name} style={gi > 0 ? { borderTop: "1px solid #f3f4f6" } : undefined}>
              <div
                onClick={() => toggleGroup(g.name)}
                style={{
                  padding: "10px 4px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 10,
                  borderRadius: 4,
                  userSelect: "none",
                  transition: "background 80ms",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#fafafa")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <span style={{
                  color: "#c4c4c8",
                  fontSize: 9,
                  width: 10,
                  display: "inline-block",
                  textAlign: "center",
                  marginTop: 4,
                }}>
                  {isOpen ? "⌄" : "›"}
                </span>
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontWeight: 500, color: "#111827", letterSpacing: -0.1 }}>
                    {g.name}
                  </span>
                  {g.rawLayers.length > 0 && (
                    <span style={{ fontSize: 10.5, color: "#9ca3af", letterSpacing: 0.1 }}>
                      {g.rawLayers.join(" · ")}
                    </span>
                  )}
                </div>
                <span style={{
                  color: "#9ca3af",
                  fontSize: 12,
                  fontVariantNumeric: "tabular-nums",
                  marginTop: 2,
                }}>
                  {g.entities.length}
                </span>
              </div>
              {isOpen && (
                <div style={{ paddingBottom: 6 }}>
                  {g.entities.map(r => (
                    <div
                      key={r.id}
                      onClick={() => onNavigate(r.navigate, r.sleeveId)}
                      style={{
                        padding: "5px 4px 5px 32px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "baseline",
                        gap: 14,
                        fontSize: 12,
                        borderRadius: 4,
                        transition: "background 80ms",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "#fafafa")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <span style={{ color: "#9ca3af", width: 64, flexShrink: 0, fontSize: 11 }}>
                        {r.typeLabel}
                      </span>
                      <span style={{ color: "#374151", fontWeight: 500, minWidth: 140, flexShrink: 0 }}>
                        {r.label}
                      </span>
                      <span style={{
                        color: "#9ca3af",
                        fontSize: 10.5,
                        letterSpacing: 0.1,
                        width: 180,
                        flexShrink: 0,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}>
                        {r.rawLayer || ""}
                      </span>
                      <span style={{
                        color: "#9ca3af",
                        flex: 1,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}>
                        {r.properties}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
