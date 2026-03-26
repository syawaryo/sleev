"""スリーブの正確な個数をカウントするスクリプト"""
import ezdxf
import os
from collections import defaultdict, Counter

def count_sleeves(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    # 1. ブロック定義数（ユニークな部品）
    block_counts = defaultdict(int)
    for block in doc.blocks:
        name = block.name
        if "スリーブ" in name:
            block_counts["スリーブ（鉄）"] += 1
        elif "箱（鉄）" in name:
            block_counts["箱（鉄）"] += 1
        elif "箱（木）" in name:
            block_counts["箱（木）"] += 1
        elif "電気パイプ" in name:
            block_counts["電気パイプ"] += 1

    # 2. INSERT参照数（実際に図面上に配置された数）
    insert_counts = defaultdict(int)
    insert_by_layer = defaultdict(lambda: defaultdict(int))
    for entity in msp:
        if entity.dxftype() == "INSERT":
            name = entity.dxf.name
            layer = entity.dxf.get("layer", "")
            if "スリーブ" in name:
                cat = "スリーブ（鉄）"
            elif "箱（鉄）" in name:
                cat = "箱（鉄）"
            elif "箱（木）" in name:
                cat = "箱（木）"
            elif "電気パイプ" in name:
                cat = "電気パイプ"
            else:
                continue
            insert_counts[cat] += 1
            insert_by_layer[cat][layer] += 1

    # 3. スリーブ関連レイヤーのエンティティも集計
    sleeve_layer_entities = defaultdict(lambda: Counter())
    for entity in msp:
        layer = entity.dxf.get("layer", "")
        if "スリーブ" in layer:
            sleeve_layer_entities[layer][entity.dxftype()] += 1

    # 4. テキストから予備スリーブ情報を探す
    yobi_texts = []
    for entity in msp:
        text = ""
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
        elif entity.dxftype() == "MTEXT":
            text = entity.text if hasattr(entity, 'text') else ""
        if text and ("予備" in text or "ヨビ" in text or "よび" in text or "YOBI" in text or "yobi" in text):
            layer = entity.dxf.get("layer", "")
            yobi_texts.append((layer, text.strip()))

    # 5. ブロック定義内のテキストも検索（予備情報）
    for block in doc.blocks:
        for entity in block:
            text = ""
            if entity.dxftype() == "TEXT":
                text = entity.dxf.get("text", "")
            elif entity.dxftype() == "MTEXT":
                text = entity.text if hasattr(entity, 'text') else ""
            if text and ("予備" in text or "ヨビ" in text or "よび" in text):
                layer = entity.dxf.get("layer", "")
                yobi_texts.append((f"BLOCK:{block.name} [{layer}]", text.strip()))

    # 出力
    print(f"\n{'='*60}")
    print(f"  {fname}")
    print(f"{'='*60}")

    print(f"\n  ブロック定義数（ユニークな部品テンプレート）:")
    for cat, cnt in sorted(block_counts.items()):
        print(f"    {cat}: {cnt}個")

    print(f"\n  INSERT配置数（図面上に実際に置かれた数）:")
    total_inserts = 0
    for cat, cnt in sorted(insert_counts.items()):
        print(f"    {cat}: {cnt}個")
        total_inserts += cnt
        for layer, lcnt in sorted(insert_by_layer[cat].items()):
            print(f"      └ [{layer}]: {lcnt}")
    print(f"    ─────────────────")
    print(f"    合計: {total_inserts}個")

    print(f"\n  スリーブ関連レイヤーの全エンティティ:")
    for layer, etypes in sorted(sleeve_layer_entities.items()):
        total = sum(etypes.values())
        etype_str = ", ".join(f"{k}:{v}" for k, v in sorted(etypes.items(), key=lambda x: -x[1]))
        print(f"    [{layer}]: {total} ({etype_str})")

    print(f"\n  予備（ヨビ）スリーブ関連テキスト:")
    if yobi_texts:
        seen = set()
        for src, text in yobi_texts:
            key = (src, text)
            if key not in seen:
                seen.add(key)
                print(f"    {src}: {text}")
        print(f"  → 予備テキスト: {len(seen)}件")
    else:
        print(f"    （見つかりませんでした）")

    # 6. スリーブ個数表テキストを探す
    print(f"\n  個数表関連テキスト（集計表のテキスト）:")
    for entity in msp:
        text = ""
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
        elif entity.dxftype() == "MTEXT":
            text = entity.text if hasattr(entity, 'text') else ""
        if text and "個数" in text:
            layer = entity.dxf.get("layer", "")
            print(f"    [{layer}] {text.strip()}")

    # ブロック内も
    for block in doc.blocks:
        for entity in block:
            text = ""
            if entity.dxftype() == "TEXT":
                text = entity.dxf.get("text", "")
            elif entity.dxftype() == "MTEXT":
                text = entity.text if hasattr(entity, 'text') else ""
            if text and ("個数" in text or "合計" in text) and "スリーブ" in text:
                print(f"    BLOCK:{block.name} {text.strip()}")

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    for fname in ["1階床スリーブ図.dxf", "2階床スリーブ図.dxf"]:
        fpath = os.path.join(dxf_dir, fname)
        if os.path.exists(fpath):
            count_sleeves(fpath, fname)

if __name__ == "__main__":
    main()
