"""1つのスリーブに付随する情報を調べるスクリプト
スリーブブロック（INSERT）の位置から近傍のテキスト・寸法線を収集する"""
import ezdxf
import os
import math
from collections import defaultdict

def distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def analyze_sleeve_info(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    # 1. スリーブブロックのINSERT位置を収集
    sleeves = []
    for entity in msp:
        if entity.dxftype() == "INSERT":
            name = entity.dxf.name
            if "スリーブ" in name or "箱（鉄）" in name or "箱（木）" in name or "電気パイプ" in name:
                pos = entity.dxf.insert
                layer = entity.dxf.get("layer", "")
                sleeves.append({
                    "name": name,
                    "layer": layer,
                    "x": pos[0],
                    "y": pos[1],
                    "type": "スリーブ" if "スリーブ" in name else "箱" if "箱" in name else "電気パイプ"
                })

    # 2. 全テキスト・寸法線の位置を収集
    texts = []
    for entity in msp:
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
            if text.strip():
                pos = entity.dxf.insert
                layer = entity.dxf.get("layer", "")
                texts.append({"text": text.strip(), "x": pos[0], "y": pos[1], "layer": layer, "type": "TEXT"})
        elif entity.dxftype() == "MTEXT":
            text = entity.text if hasattr(entity, 'text') else ""
            if text.strip():
                pos = entity.dxf.insert
                layer = entity.dxf.get("layer", "")
                texts.append({"text": text.strip(), "x": pos[0], "y": pos[1], "layer": layer, "type": "MTEXT"})

    dims = []
    for entity in msp:
        if entity.dxftype() == "DIMENSION":
            layer = entity.dxf.get("layer", "")
            defpoint = entity.dxf.get("defpoint", (0,0,0))
            defpoint2 = entity.dxf.get("defpoint2", (0,0,0))
            text_mid = entity.dxf.get("text_midpoint", (0,0,0))
            dim_text = entity.dxf.get("text", "")
            # 実測値も取得
            try:
                actual = entity.get_measurement()
            except:
                actual = None
            dims.append({
                "layer": layer,
                "defpoint": defpoint,
                "defpoint2": defpoint2,
                "text_mid": text_mid,
                "text": dim_text,
                "actual": actual
            })

    # 3. ブロック定義内のテキスト（スリーブブロック自体に含まれる情報）
    print(f"\n{'='*70}")
    print(f"  {fname}")
    print(f"{'='*70}")

    print(f"\n  【スリーブブロック自体に含まれる情報（定義内テキスト）】")
    block_info = defaultdict(list)
    for block in doc.blocks:
        if "スリーブ" in block.name or "箱" in block.name or "電気パイプ" in block.name:
            for entity in block:
                if entity.dxftype() == "TEXT":
                    text = entity.dxf.get("text", "")
                    layer = entity.dxf.get("layer", "")
                    if text.strip():
                        block_info[block.name].append((layer, "TEXT", text.strip()))
                elif entity.dxftype() == "MTEXT":
                    text = entity.text if hasattr(entity, 'text') else ""
                    layer = entity.dxf.get("layer", "")
                    if text.strip():
                        block_info[block.name].append((layer, "MTEXT", text.strip()))
                elif entity.dxftype() in ("LINE", "CIRCLE", "ARC", "LWPOLYLINE"):
                    layer = entity.dxf.get("layer", "")
                    if not any(e[0] == layer and e[1] == entity.dxftype() for e in block_info.get(block.name, [])):
                        block_info[block.name].append((layer, entity.dxftype(), "(図形要素)"))

    # 代表的なスリーブブロックの中身を詳細表示（5個）
    shown = 0
    for bname, entries in sorted(block_info.items()):
        if shown >= 5:
            break
        print(f"\n    Block: {bname}")
        for layer, etype, text in entries:
            print(f"      [{layer}] ({etype}) {text}")
        shown += 1

    if len(block_info) > 5:
        print(f"\n    ... 他 {len(block_info)-5} ブロック")

    # 4. 代表的なスリーブの近傍情報（サンプル5個）
    print(f"\n  【スリーブ周辺のテキスト・寸法（近傍500mm以内）】")
    search_radius = 500  # mm

    # P-N番号があるスリーブを優先的にピックアップ
    pn_sleeves = []
    for s in sleeves:
        for t in texts:
            if "P-N-" in t["text"] and distance((s["x"], s["y"]), (t["x"], t["y"])) < search_radius:
                pn_sleeves.append((s, t["text"]))
                break

    samples = pn_sleeves[:5] if pn_sleeves else [(s, "番号なし") for s in sleeves[:5]]

    for sleeve, pn in samples:
        sx, sy = sleeve["x"], sleeve["y"]
        print(f"\n    ● {pn} ({sleeve['name']}) at ({sx:.0f}, {sy:.0f}) [{sleeve['layer']}]")

        # 近傍テキスト
        nearby_texts = []
        for t in texts:
            d = distance((sx, sy), (t["x"], t["y"]))
            if d < search_radius:
                nearby_texts.append((d, t))

        nearby_texts.sort(key=lambda x: x[0])
        print(f"      近傍テキスト:")
        for d, t in nearby_texts[:15]:
            print(f"        {d:>6.0f}mm [{t['layer']}] {t['text']}")

        # 近傍寸法線
        nearby_dims = []
        for dim in dims:
            d1 = distance((sx, sy), (dim["defpoint"][0], dim["defpoint"][1]))
            d2 = distance((sx, sy), (dim["defpoint2"][0], dim["defpoint2"][1]))
            d_min = min(d1, d2)
            if d_min < search_radius * 3:  # 寸法線はやや広めに検索
                nearby_dims.append((d_min, dim))

        nearby_dims.sort(key=lambda x: x[0])
        print(f"      近傍寸法線:")
        for d, dim in nearby_dims[:10]:
            val = f"実測値:{dim['actual']:.1f}" if dim['actual'] else ""
            print(f"        {d:>6.0f}mm [{dim['layer']}] text=\"{dim['text']}\" {val}")

    # 5. スリーブに付随する情報のパターン集計
    print(f"\n  【スリーブ近傍テキストのレイヤー別パターン集計】")
    layer_pattern_count = defaultdict(int)
    text_pattern_count = defaultdict(int)

    for s in sleeves:
        sx, sy = s["x"], s["y"]
        for t in texts:
            d = distance((sx, sy), (t["x"], t["y"]))
            if d < search_radius:
                layer_pattern_count[t["layer"]] += 1
                # テキストパターンを分類
                txt = t["text"]
                if "P-N-" in txt:
                    text_pattern_count["P-N-xxx（管理番号）"] += 1
                elif "φ" in txt or "Φ" in txt:
                    text_pattern_count["xxxφ（径）"] += 1
                elif "A)" in txt or "A）" in txt or txt.endswith("A"):
                    text_pattern_count["xxxA（管サイズ）"] += 1
                elif "FL" in txt:
                    text_pattern_count["FL±xxx（レベル）"] += 1
                elif "外径" in txt or "外形" in txt:
                    text_pattern_count["外径xxxφ"] += 1
                elif "予備" in txt or "ヨビ" in txt:
                    text_pattern_count["予備"] += 1
                elif "追加" in txt:
                    text_pattern_count["追加"] += 1
                elif "RD" in txt:
                    text_pattern_count["RD（ルーフドレン）"] += 1
                elif any(k in txt for k in ["CW", "SP", "KD", "SD", "HS", "G(", "PUP"]):
                    text_pattern_count["配管種別記号"] += 1
                else:
                    text_pattern_count[f"その他: {txt[:20]}"] += 1

    print(f"\n    レイヤー別:")
    for layer, cnt in sorted(layer_pattern_count.items(), key=lambda x: -x[1]):
        print(f"      {cnt:>4}件 [{layer}]")

    print(f"\n    テキストパターン別:")
    for pattern, cnt in sorted(text_pattern_count.items(), key=lambda x: -x[1]):
        print(f"      {cnt:>4}件 {pattern}")

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    # まず1階だけ
    fname = "1階床スリーブ図.dxf"
    fpath = os.path.join(dxf_dir, fname)
    if os.path.exists(fpath):
        analyze_sleeve_info(fpath, fname)

if __name__ == "__main__":
    main()
