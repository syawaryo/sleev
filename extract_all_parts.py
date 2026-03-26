"""DXF内の全パーツ・コンポーネントを分類別に一覧化するスクリプト"""
import ezdxf
import os
from collections import defaultdict, Counter

def analyze_file(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    # レイヤー別エンティティ集計
    layer_entities = defaultdict(lambda: Counter())
    layer_count = defaultdict(int)

    for entity in msp:
        layer = entity.dxf.get("layer", "(なし)")
        etype = entity.dxftype()
        layer_entities[layer][etype] += 1
        layer_count[layer] += 1

    # ブロック定義内も集計
    block_texts = defaultdict(list)
    for block in doc.blocks:
        if block.name.startswith("*") or block.name.startswith("INS-"):
            continue
        for entity in block:
            layer = entity.dxf.get("layer", "(なし)")
            etype = entity.dxftype()
            if etype in ("TEXT", "MTEXT"):
                text = ""
                if etype == "TEXT":
                    text = entity.dxf.get("text", "")
                else:
                    text = entity.text if hasattr(entity, 'text') else ""

    # 分野別に分類
    categories = {
        "[基本]": {},
        "[建築]": {},
        "[空調]": {},
        "[衛生]": {},
        "[電気]": {},
        "その他": {}
    }

    for layer, count in sorted(layer_count.items(), key=lambda x: x[0]):
        matched = False
        for prefix in ["[基本]", "[建築]", "[空調]", "[衛生]", "[電気]"]:
            if layer.startswith(prefix) or (prefix == "[基本]" and layer.startswith("[基本]")):
                if layer.startswith(prefix):
                    categories[prefix][layer] = (count, dict(layer_entities[layer]))
                    matched = True
                    break
        if not matched:
            categories["その他"][layer] = (count, dict(layer_entities[layer]))

    # 出力
    print(f"\n{'='*80}")
    print(f"  {fname}")
    print(f"{'='*80}")

    for cat_name, layers in categories.items():
        if not layers:
            continue
        total = sum(v[0] for v in layers.values())
        print(f"\n{'─'*80}")
        print(f"  {cat_name} ({len(layers)}レイヤー, {total}エンティティ)")
        print(f"{'─'*80}")

        # サブカテゴリで分類
        subcats = defaultdict(list)
        for layer, (count, etypes) in sorted(layers.items()):
            # レイヤー名からサブカテゴリを推定
            name = layer
            for prefix in ["[基本]", "[建築]", "[空調]", "[衛生]", "[電気]"]:
                name = name.replace(prefix, "")

            # サブカテゴリ判定
            subcat = "その他"
            keywords = {
                "柱": "柱",
                "梁": "梁",
                "壁": "壁",
                "スラブ": "スラブ・床",
                "床": "スラブ・床",
                "デッキ": "スラブ・床",
                "天井": "天井",
                "屋根": "屋根",
                "建具": "建具・開口",
                "開口": "建具・開口",
                "スリーブ": "スリーブ・貫通",
                "貫通": "スリーブ・貫通",
                "箱": "スリーブ・貫通",
                "パイプ": "配管",
                "管": "配管",
                "配管": "配管",
                "ダクト": "ダクト",
                "風道": "ダクト",
                "寸法": "寸法・注記",
                "文字": "寸法・注記",
                "記入": "寸法・注記",
                "注記": "寸法・注記",
                "引出": "寸法・注記",
                "ハッチ": "ハッチ・塗り",
                "塗り": "ハッチ・塗り",
                "ケーブル": "ケーブル・電線",
                "電線": "ケーブル・電線",
                "ラック": "ケーブル・電線",
                "機器": "機器・器具",
                "器具": "機器・器具",
                "感知器": "機器・器具",
                "LED": "機器・器具",
                "照明": "機器・器具",
                "耐火": "耐火・防火",
                "防火": "耐火・防火",
                "消火": "消火設備",
                "スプリンクラー": "消火設備",
                "仕上": "仕上げ",
                "図枠": "図枠・表題",
                "表題": "図枠・表題",
                "タイトル": "図枠・表題",
                "C1": "図枠・表題",
                "階段": "階段・EV",
                "EV": "階段・EV",
                "エレベ": "階段・EV",
                "修飾": "修飾・装飾",
                "室名": "室名",
                "通り芯": "通り芯・基準",
                "基準": "通り芯・基準",
                "鉄骨": "鉄骨",
                "ブレース": "鉄骨",
            }
            for kw, sc in keywords.items():
                if kw in name or kw in layer:
                    subcat = sc
                    break

            subcats[subcat].append((layer, count, etypes))

        for subcat, items in sorted(subcats.items()):
            print(f"\n  【{subcat}】")
            for layer, count, etypes in items:
                etype_str = ", ".join(f"{k}:{v}" for k, v in sorted(etypes.items(), key=lambda x: -x[1]))
                print(f"    {layer:<55} {count:>5}  ({etype_str})")

    # ブロック（コンポーネント）一覧
    print(f"\n{'─'*80}")
    print(f"  名前付きブロック定義（部品・コンポーネント）")
    print(f"{'─'*80}")

    block_types = defaultdict(list)
    for block in doc.blocks:
        name = block.name
        if name.startswith("*") or name.startswith("INS-") or name.startswith("_"):
            continue

        entity_count = 0
        etypes = Counter()
        for e in block:
            entity_count += 1
            etypes[e.dxftype()] += 1

        if entity_count == 0:
            continue

        # ブロック名からカテゴリ判定
        if "スリーブ" in name:
            cat = "スリーブ"
        elif "箱（鉄）" in name or "箱（木）" in name:
            cat = "箱（開口）"
        elif "電気パイプ" in name:
            cat = "電気パイプ"
        elif "LED" in name or "灯" in name:
            cat = "照明器具"
        elif "感知器" in name:
            cat = "感知器"
        elif "スイッチ" in name or "ｽｲｯﾁ" in name:
            cat = "スイッチ・センサ"
        elif "スピーカ" in name or "ｽﾋﾟｰｶ" in name:
            cat = "音響器具"
        elif "引下" in name:
            cat = "引下げ"
        else:
            cat = "その他"

        block_types[cat].append((name, entity_count))

    for cat, blocks in sorted(block_types.items()):
        print(f"\n  【{cat}】({len(blocks)}個)")
        # 代表的なものだけ表示（多すぎる場合）
        if len(blocks) > 10:
            for name, cnt in blocks[:5]:
                print(f"    {name:<60} ({cnt}エンティティ)")
            print(f"    ... 他 {len(blocks)-5}個")
        else:
            for name, cnt in blocks:
                print(f"    {name:<60} ({cnt}エンティティ)")


def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    for fname in ["1階床スリーブ図.dxf", "2階床スリーブ図.dxf"]:
        fpath = os.path.join(dxf_dir, fname)
        if os.path.exists(fpath):
            analyze_file(fpath, fname)

if __name__ == "__main__":
    main()
