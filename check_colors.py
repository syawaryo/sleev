"""レイヤーの色設定を確認するスクリプト"""
import ezdxf
import os

# AutoCAD標準色番号→色名マッピング
ACI_COLORS = {
    1: "赤",
    2: "黄",
    3: "緑",
    4: "シアン(水色)",
    5: "青",
    6: "マゼンタ(紫)",
    7: "白/黒",
    8: "グレー(暗)",
    9: "グレー(明)",
    10: "赤(10)",
    30: "オレンジ",
    40: "黄橙",
    50: "黄緑",
    60: "緑(60)",
    70: "青緑(70)",
    80: "水色(80)",
    90: "青紫(90)",
    140: "シアン系",
    150: "青系",
    160: "青系",
    170: "紫系",
    200: "紫系",
    210: "ピンク系",
}

def color_name(c):
    if c in ACI_COLORS:
        return ACI_COLORS[c]
    if 1 <= c <= 9:
        return f"基本色{c}"
    if 10 <= c <= 19:
        return "赤系"
    if 20 <= c <= 29:
        return "オレンジ系"
    if 30 <= c <= 39:
        return "オレンジ系"
    if 40 <= c <= 49:
        return "黄系"
    if 50 <= c <= 59:
        return "黄緑系"
    if 60 <= c <= 69:
        return "緑系"
    if 70 <= c <= 79:
        return "緑系"
    if 80 <= c <= 89:
        return "青緑系"
    if 90 <= c <= 99:
        return "青緑系"
    if 100 <= c <= 119:
        return "水色系"
    if 120 <= c <= 139:
        return "水色系"
    if 140 <= c <= 159:
        return "シアン-青系"
    if 160 <= c <= 179:
        return "青系"
    if 180 <= c <= 199:
        return "青紫系"
    if 200 <= c <= 219:
        return "紫系"
    if 220 <= c <= 239:
        return "ピンク系"
    if 240 <= c <= 255:
        return "赤紫系"
    return f"色{c}"

def check_colors(fpath, fname):
    doc = ezdxf.readfile(fpath)

    print(f"\n{'='*70}")
    print(f"  {fname}")
    print(f"{'='*70}")

    # 青系・緑系のレイヤーを抽出
    print(f"\n  【青系レイヤー（色4,5,150-179）】")
    blue_layers = []
    green_layers = []
    all_layers = []

    for layer in doc.layers:
        c = layer.color
        name = layer.dxf.name
        all_layers.append((name, c, color_name(c)))

        if c == 5 or (150 <= c <= 179):
            blue_layers.append((name, c, color_name(c)))
        elif c == 4 or (100 <= c <= 139):
            blue_layers.append((name, c, color_name(c)))
        elif c == 3 or (60 <= c <= 79) or (50 <= c <= 59):
            green_layers.append((name, c, color_name(c)))

    for name, c, cname in sorted(blue_layers):
        if "スリーブ" in name or "配管" in name or "管" in name or "衛生" in name or "空調" in name or "電気" in name:
            print(f"    色{c:>3} ({cname:<10}) {name}")

    print(f"\n  【緑系レイヤー（色3,50-79）】")
    for name, c, cname in sorted(green_layers):
        if "スリーブ" in name or "配管" in name or "管" in name or "衛生" in name or "空調" in name or "電気" in name:
            print(f"    色{c:>3} ({cname:<10}) {name}")

    # 配管・スリーブ関連レイヤーの色を全部出す
    print(f"\n  【配管・スリーブ関連レイヤーの色一覧】")
    for name, c, cname in sorted(all_layers):
        if any(kw in name for kw in ["スリーブ", "配管", "管", "排水", "給水", "上水", "汚水", "雑排", "雨水", "冷水", "温水", "冷却", "冷媒", "ガス", "消火", "SP"]):
            print(f"    色{c:>3} ({cname:<10}) {name}")

    # 分野別の色も確認
    print(f"\n  【分野プレフィックス別の代表的な色】")
    prefix_colors = {}
    for name, c, cname in all_layers:
        for prefix in ["[空調]", "[衛生]", "[電気]", "[建築]", "[基本]"]:
            if name.startswith(prefix):
                if prefix not in prefix_colors:
                    prefix_colors[prefix] = {}
                if c not in prefix_colors[prefix]:
                    prefix_colors[prefix][c] = []
                prefix_colors[prefix][c].append(name)

    for prefix, colors in sorted(prefix_colors.items()):
        print(f"\n    {prefix}:")
        for c, names in sorted(colors.items(), key=lambda x: -len(x[1])):
            print(f"      色{c:>3} ({color_name(c):<10}): {len(names)}レイヤー")
            # 代表例を3つまで
            for n in names[:3]:
                print(f"        例: {n}")

def main():
    dxf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf_output")
    for fname in ["1階床スリーブ図.dxf"]:
        fpath = os.path.join(dxf_dir, fname)
        if os.path.exists(fpath):
            check_colors(fpath, fname)

if __name__ == "__main__":
    main()
