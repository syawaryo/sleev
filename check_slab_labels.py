"""スラブラベルのINSERTブロック内容を詳細に調査"""
import ezdxf
import os
from collections import defaultdict

def analyze_slab_labels(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    print(f"\n{'='*70}")
    print(f"  {fname}")
    print(f"{'='*70}")

    # F308_スラブラベル レイヤーのINSERTを探す
    slab_layers = set()
    for layer in doc.layers:
        name = layer.dxf.name
        if "F308" in name or "スラブラベル" in name or "スラブハンチ" in name:
            slab_layers.add(name)
    print(f"\n  スラブラベル関連レイヤー: {slab_layers}")

    # INSERTを収集
    inserts = []
    for entity in msp:
        if entity.dxftype() == "INSERT" and entity.dxf.layer in slab_layers:
            inserts.append(entity)

    print(f"  INSERT数: {len(inserts)}")

    # ブロック定義の中身を調査
    block_contents = defaultdict(list)
    block_names = set(e.dxf.name for e in inserts)

    print(f"  ユニークブロック名: {len(block_names)}")

    # 代表的なブロックの中身を詳細表示
    shown = 0
    for bname in sorted(block_names):
        if shown >= 10:
            break
        try:
            block = doc.blocks.get(bname)
        except:
            continue

        entities = list(block)
        if len(entities) == 0:
            continue

        # テキストがあるブロックだけ表示
        has_text = any(e.dxftype() in ("TEXT", "MTEXT") for e in entities)
        if not has_text:
            continue

        print(f"\n  Block: {bname} ({len(entities)}エンティティ)")
        for entity in entities:
            layer = entity.dxf.get("layer", "")
            etype = entity.dxftype()
            if etype == "TEXT":
                text = entity.dxf.get("text", "")
                pos = entity.dxf.insert
                print(f"    [{layer}] TEXT: \"{text}\" at ({pos.x:.0f}, {pos.y:.0f})")
            elif etype == "MTEXT":
                text = entity.text if hasattr(entity, 'text') else ""
                pos = entity.dxf.insert
                print(f"    [{layer}] MTEXT: \"{text}\" at ({pos.x:.0f}, {pos.y:.0f})")
            elif etype == "LINE":
                s = entity.dxf.start
                e_end = entity.dxf.end
                print(f"    [{layer}] LINE: ({s.x:.0f},{s.y:.0f})-({e_end.x:.0f},{e_end.y:.0f})")
            elif etype == "ARC":
                c = entity.dxf.center
                r = entity.dxf.radius
                print(f"    [{layer}] ARC: center({c.x:.0f},{c.y:.0f}) r={r:.0f}")
            elif etype == "CIRCLE":
                c = entity.dxf.center
                r = entity.dxf.radius
                print(f"    [{layer}] CIRCLE: center({c.x:.0f},{c.y:.0f}) r={r:.0f}")
            elif etype == "HATCH":
                print(f"    [{layer}] HATCH")
            elif etype == "INSERT":
                print(f"    [{layer}] INSERT: {entity.dxf.name}")
            else:
                print(f"    [{layer}] {etype}")
        shown += 1

    # 全ブロックのテキストパターンを集計
    print(f"\n  【全スラブラベルブロック内のテキストパターン】")
    all_texts = []
    for bname in block_names:
        try:
            block = doc.blocks.get(bname)
        except:
            continue
        for entity in block:
            if entity.dxftype() == "TEXT":
                text = entity.dxf.get("text", "").strip()
                if text:
                    all_texts.append(text)
            elif entity.dxftype() == "MTEXT":
                text = (entity.text if hasattr(entity, 'text') else "").strip()
                if text:
                    all_texts.append(text)

    # パターン分類
    import re
    patterns = defaultdict(list)
    for t in all_texts:
        if re.match(r'^S\d+', t):
            patterns["スラブ記号（S1, S2...）"].append(t)
        elif re.match(r'^-?\d+～-?\d+$', t) or re.match(r'^-?\d+--?\d+$', t):
            patterns["レベル範囲"].append(t)
        elif re.match(r'^\(-?\d+\)$', t):
            patterns["代表レベル（括弧）"].append(t)
        elif re.match(r'^\d+$', t) and int(t) < 500:
            patterns["スラブ厚"].append(t)
        elif re.match(r'^\(\d+\)$', t) and int(t.strip('()')) < 500:
            patterns["スラブ厚（括弧）"].append(t)
        elif t in ("t", "h", "t / h"):
            patterns["t/hラベル"].append(t)
        elif "スラブ底" in t or "FL" in t:
            patterns["FLテキスト"].append(t)
        else:
            patterns[f"その他: {t[:30]}"].append(t)

    for pattern, items in sorted(patterns.items(), key=lambda x: -len(x[1])):
        unique = sorted(set(items))
        print(f"    {pattern}: {len(items)}件")
        if len(unique) <= 15:
            print(f"      {unique}")
        else:
            print(f"      {unique[:10]} ... 他{len(unique)-10}種")

    # INSERT位置とスラブ記号の対応
    print(f"\n  【スラブ記号と配置位置（サンプル10件）】")
    count = 0
    for entity in inserts:
        if count >= 10:
            break
        bname = entity.dxf.name
        pos = entity.dxf.insert
        try:
            block = doc.blocks.get(bname)
        except:
            continue
        texts = []
        for e in block:
            if e.dxftype() == "TEXT":
                t = e.dxf.get("text", "").strip()
                if t:
                    texts.append(t)
        if texts:
            print(f"    at ({pos.x:.0f}, {pos.y:.0f}): {texts}")
            count += 1

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    for fname in ["1階床スリーブ図.dxf", "2階床スリーブ図.dxf"]:
        fpath = os.path.join(dxf_dir, fname)
        if os.path.exists(fpath):
            analyze_slab_labels(fpath, fname)

if __name__ == "__main__":
    main()
