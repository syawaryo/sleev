"""スラブラベルのLINE・CIRCLE・HATCHがINSERTとどう関係するか調査"""
import ezdxf
import os
import math
from collections import defaultdict

def analyze(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    slab_layers = set()
    for layer in doc.layers:
        if "F308" in layer.dxf.name or "スラブラベル" in layer.dxf.name:
            slab_layers.add(layer.dxf.name)

    inserts = []
    lines = []
    circles = []
    texts_outside = []  # F308レイヤーのTEXT（INSERT外）

    for entity in msp:
        if entity.dxf.layer not in slab_layers:
            continue
        if entity.dxftype() == "INSERT":
            pos = entity.dxf.insert
            # ブロック内テキスト取得
            bname = entity.dxf.name
            btexts = []
            try:
                block = doc.blocks.get(bname)
                for e in block:
                    if e.dxftype() == "TEXT":
                        t = e.dxf.get("text", "").strip()
                        if t:
                            btexts.append(t)
            except:
                pass
            inserts.append({"name": bname, "x": pos.x, "y": pos.y, "texts": btexts})
        elif entity.dxftype() == "LINE":
            s = entity.dxf.start
            e = entity.dxf.end
            length = math.hypot(e.x - s.x, e.y - s.y)
            lines.append({"sx": s.x, "sy": s.y, "ex": e.x, "ey": e.y, "len": length})
        elif entity.dxftype() == "CIRCLE":
            c = entity.dxf.center
            circles.append({"cx": c.x, "cy": c.y, "r": entity.dxf.radius})
        elif entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "").strip()
            pos = entity.dxf.insert
            texts_outside.append({"text": text, "x": pos.x, "y": pos.y})

    print(f"\n{'='*70}")
    print(f"  {fname}")
    print(f"{'='*70}")

    # LINEの長さ分布
    print(f"\n  【LINE長さ分布（{len(lines)}本）】")
    for line in sorted(lines, key=lambda x: x["len"])[:10]:
        print(f"    {line['len']:.0f}mm: ({line['sx']:.0f},{line['sy']:.0f})-({line['ex']:.0f},{line['ey']:.0f})")
    print(f"    ...")
    for line in sorted(lines, key=lambda x: x["len"])[-5:]:
        print(f"    {line['len']:.0f}mm: ({line['sx']:.0f},{line['sy']:.0f})-({line['ex']:.0f},{line['ey']:.0f})")

    # LINE・CIRCLEとINSERTの距離関係
    print(f"\n  【LINEの端点とCIRCLEの中心の近接関係】")
    # LINEの端点とCIRCLEが繋がってるか
    for line in lines[:10]:
        for circle in circles:
            d_start = math.hypot(line["sx"] - circle["cx"], line["sy"] - circle["cy"])
            d_end = math.hypot(line["ex"] - circle["cx"], line["ey"] - circle["cy"])
            if d_start < 50 or d_end < 50:
                print(f"    LINE ({line['sx']:.0f},{line['sy']:.0f})-({line['ex']:.0f},{line['ey']:.0f}) → CIRCLE at ({circle['cx']:.0f},{circle['cy']:.0f}) r={circle['r']:.0f}")
                break

    # TEXTとINSERTの関係（INSERT外のテキスト）
    print(f"\n  【INSERT外のTEXT（{len(texts_outside)}件）サンプル】")
    for t in texts_outside[:20]:
        print(f"    ({t['x']:.0f}, {t['y']:.0f}): \"{t['text']}\"")

    # スラブ底テキストの「スラブ底」は別TEXTとして存在
    print(f"\n  【\"スラブ底\" テキスト】")
    slab_bottom = [t for t in texts_outside if "スラブ底" in t["text"]]
    print(f"    {len(slab_bottom)}件")
    for t in slab_bottom[:5]:
        print(f"    ({t['x']:.0f}, {t['y']:.0f}): \"{t['text']}\"")

    # INSERT位置 vs TEXT位置 vs LINE・CIRCLEの関係を可視化
    print(f"\n  【代表的なINSERT周辺の全要素（半径5000mm）】")
    for ins in inserts[:5]:
        print(f"\n    INSERT {ins['name']} at ({ins['x']:.0f}, {ins['y']:.0f})")
        print(f"      ブロック内: {ins['texts']}")

        nearby = []
        for line in lines:
            d = min(
                math.hypot(line["sx"] - ins["x"], line["sy"] - ins["y"]),
                math.hypot(line["ex"] - ins["x"], line["ey"] - ins["y"]),
            )
            if d < 5000:
                nearby.append(("LINE", d, f"({line['sx']:.0f},{line['sy']:.0f})-({line['ex']:.0f},{line['ey']:.0f}) len={line['len']:.0f}"))
        for c in circles:
            d = math.hypot(c["cx"] - ins["x"], c["cy"] - ins["y"])
            if d < 5000:
                nearby.append(("CIRCLE", d, f"({c['cx']:.0f},{c['cy']:.0f}) r={c['r']:.0f}"))
        for t in texts_outside:
            d = math.hypot(t["x"] - ins["x"], t["y"] - ins["y"])
            if d < 5000:
                nearby.append(("TEXT", d, f"\"{t['text']}\" at ({t['x']:.0f},{t['y']:.0f})"))

        nearby.sort(key=lambda x: x[1])
        for etype, d, desc in nearby[:10]:
            print(f"      {d:>5.0f}mm {etype}: {desc}")

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    analyze(os.path.join(dxf_dir, "1階床スリーブ図.dxf"), "1階")

if __name__ == "__main__":
    main()
