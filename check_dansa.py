"""段差線とFL（スラブレベル）の関係を調べるスクリプト"""
import ezdxf
import os
import math
from collections import defaultdict

def distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def analyze_dansa(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    print(f"\n{'='*70}")
    print(f"  {fname}")
    print(f"{'='*70}")

    # 1. 段差線エンティティを収集
    dansa_entities = []
    for entity in msp:
        layer = entity.dxf.get("layer", "")
        if "段差" in layer:
            etype = entity.dxftype()
            if etype == "LINE":
                start = entity.dxf.start
                end = entity.dxf.end
                mid_x = (start[0] + end[0]) / 2
                mid_y = (start[1] + end[1]) / 2
                dansa_entities.append({
                    "layer": layer, "type": etype,
                    "x": mid_x, "y": mid_y,
                    "start": start, "end": end
                })
            elif etype == "TEXT":
                text = entity.dxf.get("text", "")
                pos = entity.dxf.insert
                dansa_entities.append({
                    "layer": layer, "type": "TEXT",
                    "x": pos[0], "y": pos[1],
                    "text": text.strip()
                })
            elif etype == "INSERT":
                pos = entity.dxf.insert
                dansa_entities.append({
                    "layer": layer, "type": "INSERT",
                    "x": pos[0], "y": pos[1],
                    "name": entity.dxf.name
                })
            elif etype == "DIMENSION":
                defpoint = entity.dxf.get("defpoint", (0,0,0))
                try:
                    actual = entity.get_measurement()
                except:
                    actual = None
                dansa_entities.append({
                    "layer": layer, "type": "DIMENSION",
                    "x": defpoint[0], "y": defpoint[1],
                    "actual": actual
                })
            elif etype in ("ARC", "LWPOLYLINE", "HATCH"):
                dansa_entities.append({
                    "layer": layer, "type": etype,
                    "x": 0, "y": 0
                })

    # 段差レイヤーのエンティティ種別集計
    print(f"\n  【段差関連レイヤーのエンティティ】")
    layer_types = defaultdict(lambda: defaultdict(int))
    for e in dansa_entities:
        layer_types[e["layer"]][e["type"]] += 1
    for layer, types in sorted(layer_types.items()):
        type_str = ", ".join(f"{t}:{c}" for t, c in sorted(types.items(), key=lambda x: -x[1]))
        print(f"    {layer}: {type_str}")

    # 段差テキストの内容
    print(f"\n  【段差記号内のテキスト（全件）】")
    dansa_texts = [e for e in dansa_entities if e["type"] == "TEXT"]
    text_patterns = defaultdict(int)
    for e in dansa_texts:
        text_patterns[e["text"]] += 1
    for text, cnt in sorted(text_patterns.items(), key=lambda x: -x[1]):
        suffix = f" x{cnt}" if cnt > 1 else ""
        print(f"    {text}{suffix}")

    # 段差寸法線の値
    print(f"\n  【段差記号内の寸法線（値）】")
    dansa_dims = [e for e in dansa_entities if e["type"] == "DIMENSION"]
    dim_values = defaultdict(int)
    for e in dansa_dims:
        if e.get("actual") is not None:
            dim_values[f"{e['actual']:.0f}mm"] += 1
    for val, cnt in sorted(dim_values.items(), key=lambda x: -x[1]):
        suffix = f" x{cnt}" if cnt > 1 else ""
        print(f"    {val}{suffix}")

    # 2. スラブレベル（FL）テキストを収集
    print(f"\n  【FL（スラブレベル）テキスト】")
    fl_texts = []
    for entity in msp:
        text = ""
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
        elif entity.dxftype() == "MTEXT":
            text = entity.text if hasattr(entity, 'text') else ""
        if "FL" in text or "スラブ底" in text or "スラブ天" in text:
            layer = entity.dxf.get("layer", "")
            pos = entity.dxf.insert
            fl_texts.append({"text": text.strip(), "x": pos[0], "y": pos[1], "layer": layer})

    fl_patterns = defaultdict(int)
    for t in fl_texts:
        fl_patterns[t["text"]] += 1
    for text, cnt in sorted(fl_patterns.items(), key=lambda x: -x[1])[:30]:
        suffix = f" x{cnt}" if cnt > 1 else ""
        print(f"    {text}{suffix}")

    # 3. 段差線の近くにFLテキストがあるか確認
    print(f"\n  【段差線(LINE)の近傍にあるFLテキスト（サンプル）】")
    dansa_lines = [e for e in dansa_entities if e["type"] == "LINE"]

    shown = 0
    for dl in dansa_lines[:200]:
        nearby_fl = []
        for ft in fl_texts:
            d = distance((dl["x"], dl["y"]), (ft["x"], ft["y"]))
            if d < 1500:
                nearby_fl.append((d, ft))
        if nearby_fl and shown < 15:
            nearby_fl.sort()
            print(f"\n    段差線 at ({dl['x']:.0f}, {dl['y']:.0f})")
            # 段差テキストも近傍から探す
            for dt in dansa_texts:
                d = distance((dl["x"], dl["y"]), (dt["x"], dt["y"]))
                if d < 500:
                    print(f"      段差テキスト {d:.0f}mm: {dt['text']}")
            for d, ft in nearby_fl[:5]:
                print(f"      FL {d:.0f}mm: [{ft['layer']}] {ft['text']}")
            shown += 1

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    fname = "1階床スリーブ図.dxf"
    fpath = os.path.join(dxf_dir, fname)
    if os.path.exists(fpath):
        analyze_dansa(fpath, fname)

if __name__ == "__main__":
    main()
