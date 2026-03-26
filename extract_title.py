"""DXFタイトルブロックから建物名・工事名を抽出するスクリプト"""
import ezdxf
import os

def extract_nested_texts(doc, layout, target_layers=None):
    """INSERT（ブロック参照）を再帰的に展開してテキストを取得"""
    results = []

    def process_insert(insert_entity, depth=0):
        block_name = insert_entity.dxf.name
        try:
            block = doc.blocks.get(block_name)
        except Exception:
            return
        for entity in block:
            layer = entity.dxf.get("layer", "")
            if entity.dxftype() == "TEXT":
                text = entity.dxf.get("text", "")
                if text.strip():
                    results.append((layer, "TEXT", text.strip(), depth))
            elif entity.dxftype() == "MTEXT":
                text = entity.text if hasattr(entity, 'text') else entity.dxf.get("text", "")
                if text.strip():
                    results.append((layer, "MTEXT", text.strip(), depth))
            elif entity.dxftype() == "INSERT":
                process_insert(entity, depth + 1)

    for entity in layout:
        layer = entity.dxf.get("layer", "")
        # タイトルブロック関連レイヤーか、全レイヤーを対象
        if target_layers and not any(t in layer for t in target_layers):
            continue
        if entity.dxftype() == "TEXT":
            text = entity.dxf.get("text", "")
            if text.strip():
                results.append((layer, "TEXT", text.strip(), 0))
        elif entity.dxftype() == "MTEXT":
            text = entity.text if hasattr(entity, 'text') else ""
            if text.strip():
                results.append((layer, "MTEXT", text.strip(), 0))
        elif entity.dxftype() == "INSERT":
            process_insert(entity)

    return results

def main():
    dxf_dir = os.path.dirname(os.path.abspath(__file__))

    # タイトルブロック関連のレイヤー
    title_layers = ["C121", "C122", "図面名称", "図面属性", "表題", "タイトル", "title"]

    for fname in ["1階床スリーブ図.dxf", "2階床スリーブ図.dxf"]:
        fpath = os.path.join(dxf_dir, "dxf_output", fname)
        if not os.path.exists(fpath):
            print(f"File not found: {fpath}")
            continue

        print(f"\n{'='*60}")
        print(f"ファイル: {fname}")
        print(f"{'='*60}")

        doc = ezdxf.readfile(fpath)
        msp = doc.modelspace()

        # 1. タイトルブロック関連レイヤーからテキスト抽出
        print("\n--- タイトルブロック関連レイヤーのテキスト ---")
        texts = extract_nested_texts(doc, msp, title_layers)
        if texts:
            for layer, etype, text, depth in texts:
                indent = "  " * depth
                print(f"  {indent}[{layer}] ({etype}) {text}")
        else:
            print("  （見つかりませんでした）")

        # 2. 工事名・物件名・建物名を含むテキストを全レイヤーから検索
        print("\n--- 工事名・物件名・建物名を含むテキスト（全レイヤー） ---")
        keywords = ["工事", "物件", "建物", "ビル", "タワー", "計画", "プロジェクト", "新築", "建設"]
        all_texts = extract_nested_texts(doc, msp)
        found = False
        for layer, etype, text, depth in all_texts:
            if any(kw in text for kw in keywords):
                print(f"  [{layer}] {text}")
                found = True
        if not found:
            print("  （見つかりませんでした）")

        # 3. 全ブロック定義内のテキストも検索
        print("\n--- ブロック定義内のキーワード検索 ---")
        for block in doc.blocks:
            for entity in block:
                text = ""
                if entity.dxftype() == "TEXT":
                    text = entity.dxf.get("text", "")
                elif entity.dxftype() == "MTEXT":
                    text = entity.text if hasattr(entity, 'text') else ""
                if text.strip() and any(kw in text for kw in keywords):
                    layer = entity.dxf.get("layer", "")
                    print(f"  Block[{block.name}] [{layer}] {text.strip()}")

if __name__ == "__main__":
    main()
