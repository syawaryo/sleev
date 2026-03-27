"""P-N-xxxテキストとスリーブINSERTの接続関係（引出線）を調査"""
import ezdxf
import os
import math
from collections import defaultdict

def analyze(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    print(f"\n{'='*70}")
    print(f"  {fname}")
    print(f"{'='*70}")

    # スリーブINSERT位置
    sleeves = []
    for entity in msp:
        if entity.dxftype() == "INSERT":
            name = entity.dxf.name
            if "スリーブ" in name:
                pos = entity.dxf.insert
                layer = entity.dxf.layer
                sleeves.append({"name": name, "x": pos.x, "y": pos.y, "layer": layer})

    # P-N-xxxテキスト
    pn_texts = []
    for entity in msp:
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "").strip()
            if "P-N-" in text:
                pos = entity.dxf.insert
                layer = entity.dxf.layer
                pn_texts.append({"text": text, "x": pos.x, "y": pos.y, "layer": layer})

    print(f"  スリーブINSERT: {len(sleeves)}個")
    print(f"  P-N-テキスト: {len(pn_texts)}個")

    # 衛生通常レイヤーのLINE（引出線の候補）
    衛生_lines = []
    for entity in msp:
        if entity.dxftype() == "LINE":
            layer = entity.dxf.layer
            if "衛生" in layer and ("通常" in layer or "スリーブ" in layer):
                s = entity.dxf.start
                e = entity.dxf.end
                衛生_lines.append({
                    "sx": s.x, "sy": s.y, "ex": e.x, "ey": e.y,
                    "layer": layer,
                    "len": math.hypot(e.x - s.x, e.y - s.y)
                })

    print(f"  衛生LINE: {len(衛生_lines)}本")

    # P-N-テキストとスリーブの距離
    print(f"\n  【P-N-テキストと最寄りスリーブの距離（サンプル20件）】")
    for pn in pn_texts[:20]:
        best_dist = float("inf")
        best_sleeve = None
        for s in sleeves:
            d = math.hypot(pn["x"] - s["x"], pn["y"] - s["y"])
            if d < best_dist:
                best_dist = d
                best_sleeve = s
        print(f"    {pn['text']:>10} at ({pn['x']:.0f},{pn['y']:.0f}) → スリーブ({best_sleeve['x']:.0f},{best_sleeve['y']:.0f}) 距離:{best_dist:.0f}mm [{pn['layer']}]")

    # P-N-テキストからスリーブへ向かう線上にLINEがあるか（引出線）
    print(f"\n  【P-N-テキスト → スリーブ間の引出線の有無（サンプル10件）】")
    for pn in pn_texts[:10]:
        # 最寄りスリーブ
        best_dist = float("inf")
        best_sleeve = None
        for s in sleeves:
            d = math.hypot(pn["x"] - s["x"], pn["y"] - s["y"])
            if d < best_dist:
                best_dist = d
                best_sleeve = s

        # この間にある引出線を探す
        connected_lines = []
        for line in 衛生_lines:
            # LINE端点がP-Nテキスト近くか
            d_pn_start = math.hypot(line["sx"] - pn["x"], line["sy"] - pn["y"])
            d_pn_end = math.hypot(line["ex"] - pn["x"], line["ey"] - pn["y"])
            # LINE端点がスリーブ近くか
            d_sl_start = math.hypot(line["sx"] - best_sleeve["x"], line["sy"] - best_sleeve["y"])
            d_sl_end = math.hypot(line["ex"] - best_sleeve["x"], line["ey"] - best_sleeve["y"])

            near_pn = min(d_pn_start, d_pn_end)
            near_sl = min(d_sl_start, d_sl_end)

            if near_pn < 1000 or near_sl < 500:
                connected_lines.append({
                    "line": line, "d_pn": near_pn, "d_sl": near_sl
                })

        print(f"\n    {pn['text']} → スリーブ({best_sleeve['x']:.0f},{best_sleeve['y']:.0f}) 距離:{best_dist:.0f}mm")
        print(f"      近傍LINE: {len(connected_lines)}本")
        for cl in connected_lines[:3]:
            l = cl["line"]
            print(f"        [{l['layer']}] ({l['sx']:.0f},{l['sy']:.0f})-({l['ex']:.0f},{l['ey']:.0f}) len={l['len']:.0f} d_pn={cl['d_pn']:.0f} d_sl={cl['d_sl']:.0f}")

    # スリーブブロック内のLINE（十字線等）の構造
    print(f"\n  【スリーブブロック内のエンティティ構造（代表3件）】")
    shown = set()
    for s in sleeves[:30]:
        if s["name"] in shown:
            continue
        try:
            block = doc.blocks.get(s["name"])
        except:
            continue
        entities = list(block)
        if len(entities) < 2:
            continue
        shown.add(s["name"])
        if len(shown) > 3:
            break
        print(f"\n    Block: {s['name']} ({len(entities)}エンティティ)")
        for e in entities:
            layer = e.dxf.get("layer", "")
            etype = e.dxftype()
            if etype == "CIRCLE":
                c = e.dxf.center
                print(f"      [{layer}] CIRCLE r={e.dxf.radius:.0f} at ({c.x:.0f},{c.y:.0f})")
            elif etype == "LINE":
                s2 = e.dxf.start
                e2 = e.dxf.end
                print(f"      [{layer}] LINE ({s2.x:.0f},{s2.y:.0f})-({e2.x:.0f},{e2.y:.0f})")
            else:
                print(f"      [{layer}] {etype}")

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    analyze(os.path.join(dxf_dir, "1階床スリーブ図.dxf"), "1階")

if __name__ == "__main__":
    main()
