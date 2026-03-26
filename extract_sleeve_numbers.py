"""スリーブの管理番号（P-N-xxxなど）を抽出するスクリプト"""
import ezdxf
import os
import re
from collections import defaultdict, Counter

def extract_sleeve_numbers(fpath, fname):
    doc = ezdxf.readfile(fpath)
    msp = doc.modelspace()

    # スリーブ関連レイヤーと全レイヤーからテキストを収集
    all_texts = []

    for entity in msp:
        text = ""
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
        elif entity.dxftype() == "MTEXT":
            text = entity.text if hasattr(entity, 'text') else ""
        if text.strip():
            layer = entity.dxf.get("layer", "")
            x = entity.dxf.get("insert", (0, 0, 0))[0] if hasattr(entity.dxf, 'insert') else 0
            y = entity.dxf.get("insert", (0, 0, 0))[1] if hasattr(entity.dxf, 'insert') else 0
            all_texts.append((layer, text.strip(), x, y))

    # ブロック内テキストも（スリーブブロック定義内）
    block_texts = []
    for block in doc.blocks:
        if block.name.startswith("*") and not block.name.startswith("*Model_Space"):
            continue
        for entity in block:
            text = ""
            if entity.dxftype() == "TEXT":
                text = entity.dxf.get("text", "")
            elif entity.dxftype() == "MTEXT":
                text = entity.text if hasattr(entity, 'text') else ""
            if text.strip():
                layer = entity.dxf.get("layer", "")
                block_texts.append((block.name, layer, text.strip()))

    print(f"\n{'='*70}")
    print(f"  {fname}")
    print(f"{'='*70}")

    # 1. P-N-xxx パターン検索
    print(f"\n  【P-N-xxx パターン】")
    pn_pattern = re.compile(r'[A-Z]-[A-Z]-\d+|[A-Z]-\d+|P-[A-Z]-\d+|[A-Z]{1,3}-\d{1,4}')
    pn_found = defaultdict(list)
    for layer, text, x, y in all_texts:
        matches = pn_pattern.findall(text)
        for m in matches:
            pn_found[layer].append(m)

    for layer, nums in sorted(pn_found.items()):
        if "スリーブ" in layer or "衛生" in layer or "空調" in layer or "電気" in layer:
            # ソートして表示
            unique = sorted(set(nums))
            print(f"    [{layer}] ({len(nums)}件, ユニーク{len(unique)}件)")
            # 番号体系を分類
            prefixes = defaultdict(list)
            for n in unique:
                parts = n.rsplit('-', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    prefixes[parts[0]].append(int(parts[1]))
                else:
                    prefixes["その他"].append(n)

            for prefix, numbers in sorted(prefixes.items()):
                if prefix == "その他":
                    print(f"      {prefix}: {numbers}")
                else:
                    numbers.sort()
                    print(f"      {prefix}: {numbers[0]}～{numbers[-1]} ({len(numbers)}個)")
                    # 欠番チェック
                    if len(numbers) > 1:
                        expected = set(range(numbers[0], numbers[-1]+1))
                        actual = set(numbers)
                        missing = sorted(expected - actual)
                        if missing:
                            print(f"        欠番: {missing}")

    # 2. スリーブレイヤーの全テキストをそのまま出力（番号体系の把握用）
    print(f"\n  【スリーブレイヤーの全テキスト（サンプル）】")
    sleeve_texts = [(layer, text) for layer, text, x, y in all_texts
                    if "スリーブ" in layer]

    # テキストパターンを集計
    patterns = Counter()
    for layer, text in sleeve_texts:
        patterns[(layer, text)] += 1

    for (layer, text), count in sorted(patterns.items()):
        suffix = f" x{count}" if count > 1 else ""
        print(f"    [{layer}] {text}{suffix}")

    # 3. 全レイヤーからスリーブ番号っぽいもの（P-, N-, K-, S- で始まる番号）
    print(f"\n  【全レイヤーからのスリーブ番号候補】")
    sleeve_num_pattern = re.compile(r'^[A-Z]{1,2}-[A-Z]{1,2}-\d{1,4}$')
    found_nums = defaultdict(list)
    for layer, text, x, y in all_texts:
        if sleeve_num_pattern.match(text):
            found_nums[layer].append(text)

    for layer, nums in sorted(found_nums.items()):
        unique = sorted(set(nums))
        prefixes = defaultdict(list)
        for n in unique:
            parts = n.rsplit('-', 1)
            if len(parts) == 2 and parts[1].isdigit():
                prefixes[parts[0]].append(int(parts[1]))

        for prefix, numbers in sorted(prefixes.items()):
            numbers.sort()
            print(f"    [{layer}] {prefix}: {numbers[0]}～{numbers[-1]} ({len(numbers)}個)")
            if len(numbers) > 1:
                expected = set(range(numbers[0], numbers[-1]+1))
                actual = set(numbers)
                missing = sorted(expected - actual)
                if missing and len(missing) <= 20:
                    print(f"      欠番: {missing}")
                elif missing:
                    print(f"      欠番: {len(missing)}個")

    # 4. ブロック定義内のスリーブ番号
    print(f"\n  【ブロック定義内のスリーブ番号】")
    for bname, layer, text in block_texts:
        if ("スリーブ" in bname or "箱" in bname or "電気パイプ" in bname):
            if sleeve_num_pattern.match(text) or pn_pattern.match(text):
                print(f"    Block[{bname}] [{layer}] {text}")

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    for fname in ["1階床スリーブ図.dxf", "2階床スリーブ図.dxf"]:
        fpath = os.path.join(dxf_dir, fname)
        if os.path.exists(fpath):
            extract_sleeve_numbers(fpath, fname)

if __name__ == "__main__":
    main()
