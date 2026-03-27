"""スリーブ近傍に配管種別が記載されているか確認するスクリプト"""
import ezdxf
import os
import math
from collections import defaultdict

def distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def check_pipe_types(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    # 配管種別キーワード
    pipe_keywords = [
        "CW", "CWW", "CDW", "HW", "HWR",  # 冷水・温水系
        "SP", "SPD",  # スプリンクラー
        "KD", "KV",  # 空調ドレン
        "RD",  # ルーフドレン
        "SD",  # 雑排水
        "HS",  # 排水
        "P-UP", "PUP",  # ポンプアップ
        "G(", "G（",  # ガス
        "汚水", "雑排水", "雨水", "上水", "給水", "給湯",
        "冷水", "温水", "冷却水", "冷媒",
        "消火", "スプリンクラー",
        "厨房排水", "湧水",
        "排気", "給気", "還気",
    ]

    # スリーブINSERT位置
    sleeves = []
    for entity in msp:
        if entity.dxftype() == "INSERT":
            name = entity.dxf.name
            if "スリーブ" in name or "箱（鉄）" in name or "箱（木）" in name or "電気パイプ" in name:
                pos = entity.dxf.insert
                layer = entity.dxf.get("layer", "")
                sleeves.append({
                    "name": name, "layer": layer,
                    "x": pos[0], "y": pos[1],
                })

    # 全テキスト
    texts = []
    for entity in msp:
        text = ""
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
        elif entity.dxftype() == "MTEXT":
            text = entity.text if hasattr(entity, 'text') else ""
        if text.strip():
            pos = entity.dxf.insert
            layer = entity.dxf.get("layer", "")
            texts.append({"text": text.strip(), "x": pos[0], "y": pos[1], "layer": layer})

    print(f"\n{'='*70}")
    print(f"  {fname}")
    print(f"{'='*70}")

    # 各スリーブに対して配管種別テキストを検索
    radii = [500, 1000, 1500, 2000, 3000]

    for radius in radii:
        has_pipe_type = 0
        no_pipe_type = 0
        no_pipe_sleeves = []

        for s in sleeves:
            sx, sy = s["x"], s["y"]
            found = False
            found_text = ""
            for t in texts:
                d = distance((sx, sy), (t["x"], t["y"]))
                if d < radius:
                    for kw in pipe_keywords:
                        if kw in t["text"]:
                            found = True
                            found_text = t["text"]
                            break
                if found:
                    break

            if found:
                has_pipe_type += 1
            else:
                no_pipe_type += 1
                # 近傍のP-N番号を探す
                pn = ""
                for t in texts:
                    d = distance((sx, sy), (t["x"], t["y"]))
                    if d < 500 and "P-N-" in t["text"]:
                        pn = t["text"]
                        break
                no_pipe_sleeves.append((s, pn))

        total = has_pipe_type + no_pipe_type
        pct = has_pipe_type / total * 100 if total > 0 else 0
        print(f"\n  検索半径 {radius}mm: {has_pipe_type}/{total} ({pct:.0f}%) に配管種別あり")

    # 最も広い半径でも配管種別がないスリーブの詳細
    print(f"\n  【配管種別が見つからないスリーブ（半径3000mm）の近傍テキスト】")
    radius = 3000
    count = 0
    for s in sleeves:
        sx, sy = s["x"], s["y"]
        found_pipe = False
        for t in texts:
            d = distance((sx, sy), (t["x"], t["y"]))
            if d < radius:
                for kw in pipe_keywords:
                    if kw in t["text"]:
                        found_pipe = True
                        break
            if found_pipe:
                break

        if not found_pipe:
            # P-N番号
            pn = ""
            nearby = []
            for t in texts:
                d = distance((sx, sy), (t["x"], t["y"]))
                if d < 500 and "P-N-" in t["text"]:
                    pn = t["text"]
                if d < 1000:
                    nearby.append((d, t["layer"], t["text"]))

            nearby.sort()
            if count < 10:
                print(f"\n    ● {pn or '番号なし'} ({s['name']}) [{s['layer']}] at ({sx:.0f}, {sy:.0f})")
                for d, layer, text in nearby[:8]:
                    print(f"        {d:>6.0f}mm [{layer}] {text}")
            count += 1

    if count > 10:
        print(f"\n    ... 他 {count - 10}件")
    print(f"\n    配管種別なし合計: {count}件")

    # 配管種別の出現パターン
    print(f"\n  【スリーブ近傍で見つかった配管種別（半径1000mm）】")
    pipe_found = defaultdict(int)
    for s in sleeves:
        sx, sy = s["x"], s["y"]
        for t in texts:
            d = distance((sx, sy), (t["x"], t["y"]))
            if d < 1000:
                for kw in pipe_keywords:
                    if kw in t["text"]:
                        pipe_found[kw] += 1

    for kw, cnt in sorted(pipe_found.items(), key=lambda x: -x[1]):
        print(f"      {cnt:>4}件 {kw}")

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    fname = "1階床スリーブ図.dxf"
    fpath = os.path.join(dxf_dir, fname)
    if os.path.exists(fpath):
        check_pipe_types(fpath, fname)

if __name__ == "__main__":
    main()
