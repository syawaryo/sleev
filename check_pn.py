"""P-N-14, P-N-15, P-N-93 が存在するか確認"""
import ezdxf
import os
import re

def check_pn(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()
    targets = ["P-N-14", "P-N-15", "P-N-93"]

    print(f"\n{'='*60}")
    print(f"  {fname}")
    print(f"{'='*60}")

    # ModelSpace内の全テキストを検索
    print("\n  【ModelSpace内のテキスト検索】")
    for entity in msp:
        text = ""
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
        elif entity.dxftype() == "MTEXT":
            text = entity.text if hasattr(entity, 'text') else ""
        if not text.strip():
            continue
        for t in targets:
            # 完全一致 or 前後に数字がない形で含まれるか
            if t in text:
                layer = entity.dxf.get("layer", "")
                x = entity.dxf.get("insert", (0,0,0))[0] if hasattr(entity.dxf, 'insert') else 0
                y = entity.dxf.get("insert", (0,0,0))[1] if hasattr(entity.dxf, 'insert') else 0
                print(f"    FOUND: [{layer}] \"{text.strip()}\" at ({x:.0f}, {y:.0f})")

    # 全ブロック内も検索
    print("\n  【ブロック定義内のテキスト検索】")
    for block in doc.blocks:
        for entity in block:
            text = ""
            if entity.dxftype() == "TEXT":
                text = entity.dxf.get("text", "")
            elif entity.dxftype() == "MTEXT":
                text = entity.text if hasattr(entity, 'text') else ""
            if not text.strip():
                continue
            for t in targets:
                if t in text:
                    layer = entity.dxf.get("layer", "")
                    print(f"    FOUND: Block[{block.name}] [{layer}] \"{text.strip()}\"")

    # P-N-1x, P-N-9x 周辺の番号も確認
    print("\n  【P-N-10～P-N-20 の存在確認】")
    pn_pattern = re.compile(r'P-N-(\d+)')
    pn_numbers = set()
    for entity in msp:
        text = ""
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
        elif entity.dxftype() == "MTEXT":
            text = entity.text if hasattr(entity, 'text') else ""
        matches = pn_pattern.findall(text)
        for m in matches:
            pn_numbers.add(int(m))

    for i in range(10, 21):
        status = "✓ あり" if i in pn_numbers else "✗ なし"
        print(f"    P-N-{i}: {status}")

    print(f"\n  【P-N-85～P-N-100 の存在確認】")
    for i in range(85, 101):
        status = "✓ あり" if i in pn_numbers else "✗ なし"
        print(f"    P-N-{i}: {status}")

    print(f"\n  【P-N 全番号リスト（ソート済み）】")
    sorted_nums = sorted(pn_numbers)
    print(f"    {sorted_nums}")
    print(f"    合計: {len(sorted_nums)}個")

    # 欠番
    if sorted_nums:
        full_range = set(range(sorted_nums[0], sorted_nums[-1]+1))
        missing = sorted(full_range - pn_numbers)
        print(f"    欠番: {missing}")

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    for fname in ["1階床スリーブ図.dxf", "2階床スリーブ図.dxf"]:
        fpath = os.path.join(dxf_dir, fname)
        if os.path.exists(fpath):
            check_pn(fpath, fname)

if __name__ == "__main__":
    main()
