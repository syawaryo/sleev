# スリーブチェッカー設計書

## 概要

DXF形式のスリーブ施工図を読み込み、15項目のチェック基準のうち14項目（#1根拠図照合を除く）を自動チェックするツール。2F DXFをメインにチェックし、#6（下階壁干渉）のみ1F DXFを参照する。

## 技術スタック

- **言語**: Python
- **DXFパース**: ezdxf
- **UI**: Streamlit（プロトタイプ。後でTypeScript UIに差し替え可能）
- **描画**: matplotlib（図面ビュー）

## ファイル構成

```
Takenakaver4/
  sleeve_checker/
    __init__.py
    models.py      — データクラス定義
    parser.py      — DXF → FloorData変換
    checks.py      — 14項目のチェック関数
  app.py           — Streamlit UI
  requirements.txt — ezdxf, streamlit, matplotlib
```

## アーキテクチャ

2層分離構成。チェックロジックはDXF非依存で、parser.pyがDXFの知識を閉じ込める。

```
DXFファイル → parser.py → FloorData（データクラス） → checks.py → CheckResult[]
                                                                        ↓
                                                              app.py（Streamlit UI）
                                                              ├ 結果サマリ
                                                              ├ 図面ビュー（matplotlib）
                                                              └ 一覧テーブル
```

## データモデル（models.py）

```python
@dataclass
class Sleeve:
    id: str                     # ブロック名 (スリーブ(S)-Z78Q3)
    center: tuple[float, float] # XY座標(mm)
    diameter: float             # スリーブ径(mm) ブロック内CIRCLEのradius×2
    label_text: str | None      # 近傍テキスト ("CW φ75", "125φ(外径140φ)50A")
    fl_text: str | None         # FLテキスト ("FL-710")
    pn_number: str | None       # P-N番号 ("P-N-1")
    layer: str                  # 元レイヤー名
    discipline: str             # "衛生" / "空調" / "電気" / "建築"

@dataclass
class GridLine:
    axis_label: str   # "1","2"..."8" or "A","B"..."F"
    direction: str    # "H" or "V"
    position: float   # H→Y座標, V→X座標

@dataclass
class DimLine:
    layer: str
    measurement: float
    defpoint1: tuple[float, float]  # 起点座標
    defpoint2: tuple[float, float]  # 終点座標
    text_override: str | None       # テキストオーバーライド（表記統一チェック用）

@dataclass
class WallLine:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str
    wall_type: str    # "RC" / "LGS" / "ALC" / "PCa" / "パネル" / "不明"

@dataclass
class StepLine:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str        # 段差線 or ヌスミ線

@dataclass
class ColumnLine:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str        # RC柱 / S柱 / 壁仕上げ

@dataclass
class FloorData:
    sleeves: list[Sleeve]
    grid_lines: list[GridLine]
    dim_lines: list[DimLine]
    wall_lines: list[WallLine]
    step_lines: list[StepLine]
    column_lines: list[ColumnLine]
    slab_level: str | None        # "スラブ天 FL-750" 等

@dataclass
class CheckResult:
    check_id: int          # 1-14
    check_name: str        # "口径・外径記載"
    severity: str          # "NG" / "WARNING" / "OK"
    sleeve: Sleeve | None  # 対象スリーブ（全体チェックならNone）
    message: str           # "FL記載なし" 等
    related_coords: list[tuple[float, float]]  # 図面ハイライト用座標
```

## パーサー（parser.py）

### レイヤー検索ルール

レイヤー名の接頭辞（`[空調]`/`[建築]`等）は図面によって異なるため、後半部分（サフィックス）で検索する。

| 取得データ | 検索キーワード | 備考 |
|-----------|--------------|------|
| 通り芯 | `C131_通心` or `C131_通芯` | LINE。H/Vはdx/dy比で判別 |
| 通り芯ラベル | `C141_通心記号` or `C141_通芯ラベル` | TEXT。番号("1","A"等) |
| 壁心 | `C151_壁心` | LINE |
| RC壁外形 | `F106_RC壁` | LINE |
| RC柱外形 | `F102_RC柱` | LINE |
| S柱外形 | `F201_Ｓ柱` | LINE |
| 壁仕上げ | `A521_壁：仕上` | LINE |
| ALC壁面 | `A422_壁：ＡＬＣ` | LINE |
| 段差線 | `F108_3_RCスラブ段差線` | LINE |
| ヌスミ線 | `F108_5_床ヌスミ` | LINE |
| スリーブ | レイヤー名に`スリーブ`を含む | INSERT → ブロック内CIRCLE radius×2 = 径 |
| 寸法線 | 全レイヤーのDIMENSION | defpoint座標で起点・終点を取得 |

### スリーブINSERTの構造

- 各スリーブは一意のブロック名（`スリーブ(S)-Z{uid}` / `スリーブ（鉄）-Z{uid}`）を持つ
- ブロック定義内にCIRCLE（半径=スリーブ径/2）+ LINE×2（十字線）
- INSERT座標 = スリーブ中心座標
- ATTRIBなし。サイズ・種別はブロック外のTEXTエンティティで表現

### テキスト紐付け

1. **ラベルテキスト**（`CW φ75` 等）: 同レイヤー(`[衛生]スリーブ`等)内のTEXTから、最近傍マッチ（Y座標優先）
2. **P-N番号**: 後述のゾーンソートロジックで自動割り当て

### P-N番号の自動紐付けロジック

P-N番号はスリーブとは別レイヤー(`[衛生]通常`)にあり、引出線等の図形的接続がないため、以下の規則で紐付ける。

**規則**: 通り芯グリッドゾーンごとに、Y範囲を上から下に処理し、縦列・横一列を判定しながら番号を振る。

1. 通り芯でグリッドゾーンを定義（X方向×Y方向の矩形区画）
2. ゾーンを右上→左下の順にソート（X降順 → Y降順）
3. ゾーン内の処理（上のY範囲から順に）:
   a. 同じY範囲内に縦列（Y方向に2個以上連続）が複数あれば、右の縦列→左の縦列の順で処理。各縦列内は上→下
   b. 縦列に属さず、X方向に連続して並んでいるもの（横一列）は左→右で処理
   c. Y範囲を1段下げて同様に繰り返す
4. P-N番号もテキスト座標で同じソートを行い、1対1対応

**縦列判定**: X座標の差が一定以内（例: 300mm）かつY方向に2個以上並んでいる
**横一列判定**: 縦列に属さず、X方向に隣接して連続している

※ 欠番（2Fに存在しないP-N番号）は1Fのみに存在するスリーブ。2Fの紐付けには影響しない。
※ 追加分（末尾の番号）やヨビ（予備）スリーブは通常の番号付け完了後に処理。
※ このロジックは実データで検証しながら反復的に調整する。完全自動が困難な場合はStreamlit UI上で手動補正できるようにする。

## チェックロジック（checks.py）

### 共通パラメータ

```python
COORD_TOLERANCE = 5.0    # 座標一致判定の許容差(mm)
DIM_SUM_TOLERANCE = 1.0  # 寸法合計の許容差(mm)
TEXT_SEARCH_RADIUS = 1000.0  # テキスト紐付けの検索半径(mm)

# 壁厚仮定値（UI側で変更可能）
WALL_THICKNESS = {
    "RC": None,       # 外形線使用（仮定不要）
    "LGS": 150.0,
    "ALC": 150.0,
    "PCa": 200.0,
    "パネル": 100.0,
    "不明": 200.0,
}

# 排水系スリーブ種別コード
DRAIN_CODES = ["SD", "RD", "WD", "排水", "汚水", "雨水"]
```

### チェック一覧

| # | カテゴリ | 関数 | 入力 | 判定 |
|---|---------|------|------|------|
| #1 | 整合性 | — | — | **対象外**（根拠図なし） |
| #2 | 整合性 | `check_discipline` | Sleeve.label_text, Sleeve.discipline | ラベルに種別コード(CW,SD等)がない → NG |
| #3 | 整合性 | `check_diameter_label` | Sleeve.label_text | `φ\d+` パターンがない → NG |
| #4 | 整合性 | `check_dim_sum` | DimLine[], GridLine[] | 通り芯間のDIM合計 ≠ 通り芯間距離(±1mm) → NG |
| #5 | 整合性 | `check_gradient` | Sleeve(排水系), 近傍TEXT | 排水スリーブに勾配テキスト(`1/\d+`)やFL値がない → WARNING |
| #6 | 整合性 | `check_lower_wall` | 2F Sleeve[], 1F WallLine[] | スリーブ中心と壁線の距離 < スリーブ半径+壁厚/2 → NG。RC壁は外形線使用、その他は壁心+壁厚仮定値で判定。座標系は1F/2F共通（通り芯座標一致確認済み）のため直接比較可能 |
| #7 | 整合性 | `check_step_slab` | Sleeve, StepLine[] | スリーブ中心と段差線の距離 < しきい値(UI設定) → WARNING。しきい値のデフォルトは空欄（ユーザーが構造基準に合わせて設定） |
| #8 | 施工図表現 | `check_fl_label` | Sleeve近傍TEXT | `FL[±+-]\d+` がない → NG |
| #9 | 施工図表現 | `check_both_sides` | Sleeve, DimLine[], GridLine[] | X/Y各方向で片側の通り芯からしか寸法がない → NG |
| #10 | 施工図表現 | `check_step_dim` | DimLine.defpoint, StepLine[] | 寸法起点が段差線/ヌスミ線上(±5mm) → NG |
| #11 | 施工図表現 | `check_sleeve_center_dim` | DimLine.defpoint, Sleeve.center | 寸法起点がスリーブ中心(±5mm) かつ終点が別スリーブ中心 → NG |
| #12 | 施工図表現 | `check_column_wall_dim` | DimLine.defpoint, ColumnLine[] | 寸法起点が柱面(`F102_RC柱`,`F201_Ｓ柱`)または壁仕上面(`A521_壁：仕上`,`A422_壁：ＡＬＣ`)上(±5mm) → NG |
| #13 | 施工図表現 | `check_dim_notation` | スリーブ近傍DimLine[] | DIMENSION表記フォーマット（カンマ区切り、単位有無、小数桁数）の多数派からの逸脱 → WARNING |
| #14 | 施工図表現 | `check_sleeve_number` | Sleeve.pn_number | P-N番号が紐付けられていない → NG |

## Streamlit UI（app.py）

### 画面構成

```
┌─────────────────────────────────────┐
│  スリーブチェッカー                    │
├─────────────────────────────────────┤
│  [2F DXFアップロード]                 │
│  [1F DXFアップロード] (下階壁干渉用)   │
│  サイドバー: 壁厚設定、しきい値設定    │
│  [チェック実行]                       │
├─────────────────────────────────────┤
│  ■ 結果サマリ                        │
│  NG: XX件  WARNING: XX件  OK: XX件   │
├─────────────────────────────────────┤
│  ■ 図面ビュー (matplotlib)            │
│  通り芯・壁・スリーブを描画           │
│  NG=赤丸  WARNING=黄丸  OK=緑丸      │
├─────────────────────────────────────┤
│  ■ 一覧テーブル                      │
│  フィルタ: [全て/NG/WARNING/OK]       │
│  スリーブID|P-N|径|位置|チェック結果   │
└─────────────────────────────────────┘
```

### UI設定項目（サイドバー）

- 壁厚仮定値（LGS/ALC/PCa/パネル/不明）
- #7 段差スラブしきい値
- 座標許容差（デフォルト5mm）
- テキスト検索半径（デフォルト1000mm）

## DXFデータ上の注意点

### 1F/2Fのレイヤー接頭辞の違い

同じデータが図面によって異なる接頭辞を持つ。

| データ | 1F | 2F |
|--------|----|----|
| 通り芯 | `[空調]C131_通心` | `[建築]C131_通心` |
| 壁心 | `[空調]C151_壁心` | `[建築]C151_壁心` |
| 段差線 | `[空調]F108_3_RCスラブ段差線` | `[建築]F108_3_RCスラブ段差線` |
| スリーブ | `[衛生]スリーブ` | `[衛生]スリーブ`（同じ） |

→ レイヤー検索はサフィックス（後半部分）で行い、接頭辞に依存しない。

### スリーブブロック名の違い

| 図面 | ブロック名パターン |
|------|------------------|
| 1F | `スリーブ（鉄）-Z{uid}` / `箱（鉄）-Z{uid}` |
| 2F | `スリーブ(S)-Z{uid}` |

→ `スリーブ` を含むブロック名で共通検索。

### テキスト形式の違い

| 図面 | ラベル形式 | FL形式 |
|------|-----------|--------|
| 1F | `125φ(外径140φ)50A` | `FL-710`（別TEXT） |
| 2F | `CW φ75` | 別レイヤーまたはなし |

→ 複数のパターンに対応する正規表現で解析。

### 座標系

- 単位: mm（1:1）
- 通り芯座標は1F/2F完全一致（オフセットなし）
- 主要建物範囲: X=0~80,000, Y=0~34,000
- 負のX/Y座標域に詳細図・凡例がある（チェック対象外）
