"""スラブラベルの矢印（引出線）の構造を調査"""
import ezdxf
import os
from collections import defaultdict

def analyze(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    print(f"\n{'='*70}")
    print(f"  {fname}")
    print(f"{'='*70}")

    # F308レイヤーの全エンティティ種別
    slab_layers = set()
    for layer in doc.layers:
        if "F308" in layer.dxf.name or "スラブラベル" in layer.dxf.name:
            slab_layers.add(layer.dxf.name)

    print(f"\n  レイヤー: {slab_layers}")

    types = defaultdict(int)
    for entity in msp:
        if entity.dxf.layer in slab_layers:
            types[entity.dxftype()] += 1
    print(f"  エンティティ種別: {dict(types)}")

    # INSERTの位置と、同レイヤーのLINEの関係を調べる
    inserts = []
    lines = []
    circles = []
    hatches = []
    texts = []

    for entity in msp:
        if entity.dxf.layer not in slab_layers:
            continue
        if entity.dxftype() == "INSERT":
            pos = entity.dxf.insert
            inserts.append({"name": entity.dxf.name, "x": pos.x, "y": pos.y})
        elif entity.dxftype() == "LINE":
            s = entity.dxf.start
            e = entity.dxf.end
            lines.append({"sx": s.x, "sy": s.y, "ex": e.x, "ey": e.y})
        elif entity.dxftype() == "CIRCLE":
            c = entity.dxf.center
            circles.append({"cx": c.x, "cy": c.y, "r": entity.dxf.radius})
        elif entity.dxftype() == "HATCH":
            hatches.append(entity)
        elif entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
            pos = entity.dxf.insert
            texts.append({"text": text, "x": pos.x, "y": pos.y})

    print(f"\n  INSERT: {len(inserts)}, LINE: {len(lines)}, CIRCLE: {len(circles)}, HATCH: {len(hatches)}, TEXT: {len(texts)}")

    # INSERTとLINEの接続関係を調べる
    # LINE端点がINSERT位置の近くにあるか
    import math
    print(f"\n  【INSERT位置とLINE端点の近接関係（サンプル10件）】")
    shown = 0
    for ins in inserts[:20]:
        connected_lines = []
        for line in lines:
            # LINE端点とINSERT位置の距離
            d_start = math.hypot(line["sx"] - ins["x"], line["sy"] - ins["y"])
            d_end = math.hypot(line["ex"] - ins["x"], line["ey"] - ins["y"])
            if d_start < 2000 or d_end < 2000:
                connected_lines.append({
                    "line": line,
                    "d_start": d_start,
                    "d_end": d_end,
                    "far_x": line["ex"] if d_start < d_end else line["sx"],
                    "far_y": line["ey"] if d_start < d_end else line["sy"],
                })

        if connected_lines and shown < 10:
            # ブロック内テキストを取得
            try:
                block = doc.blocks.get(ins["name"])
                btexts = []
                for e in block:
                    if e.dxftype() == "TEXT":
                        t = e.dxf.get("text", "").strip()
                        if t:
                            btexts.append(t)
            except:
                btexts = []

            print(f"\n    INSERT {ins['name']} at ({ins['x']:.0f}, {ins['y']:.0f})")
            print(f"      ブロック内テキスト: {btexts}")
            print(f"      接続LINE: {len(connected_lines)}本")
            for cl in connected_lines[:5]:
                near = "start" if cl["d_start"] < cl["d_end"] else "end"
                far_dist = max(cl["d_start"], cl["d_end"])
                print(f"        LINE ({cl['line']['sx']:.0f},{cl['line']['sy']:.0f})-({cl['line']['ex']:.0f},{cl['line']['ey']:.0f})")
                print(f"          近い端: {near} ({min(cl['d_start'], cl['d_end']):.0f}mm), 遠い端→({cl['far_x']:.0f},{cl['far_y']:.0f}) ({far_dist:.0f}mm)")
            shown += 1

    # CIRCLEの役割（矢印の先端？）
    print(f"\n  【CIRCLE（矢印先端？）のサイズ分布】")
    radii = defaultdict(int)
    for c in circles:
        r = round(c["r"])
        radii[r] += 1
    for r, cnt in sorted(radii.items()):
        print(f"    r={r}mm: {cnt}個")

    # HATCHの役割
    print(f"\n  【HATCH数: {len(hatches)}】")
    if hatches:
        try:
            h = hatches[0]
            print(f"    パターン名: {h.dxf.get('pattern_name', 'N/A')}")
        except:
            pass

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    fname = "1階床スリーブ図.dxf"
    fpath = os.path.join(dxf_dir, fname)
    if os.path.exists(fpath):
        analyze(fpath, fname)

if __name__ == "__main__":
    main()
