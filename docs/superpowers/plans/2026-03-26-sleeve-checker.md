# Sleeve Checker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DXFスリーブ施工図の14項目自動チェック + Streamlit UIでの結果表示

**Architecture:** parser.py(DXF→データ構造) → checks.py(チェックロジック) → app.py(Streamlit UI)。DXFの知識はparserに閉じ込め、checksはデータクラスのみ受け取る。

**Tech Stack:** Python, ezdxf, streamlit, matplotlib

**Spec:** `docs/superpowers/specs/2026-03-26-sleeve-checker-design.md`

**Test data:** `dxf_output/1階床スリーブ図.dxf`, `dxf_output/2階床スリーブ図.dxf`

---

## File Structure

```
sleeve_checker/
  __init__.py          — パッケージ初期化
  models.py            — dataclass定義 (Sleeve, GridLine, DimLine, WallLine, StepLine, ColumnLine, FloorData, CheckResult)
  parser.py            — DXF→FloorData変換。レイヤー検索、INSERT解析、テキスト紐付け、P-N番号紐付け
  checks.py            — 13チェック関数 (#2-#14) + run_all_checks()
  geometry.py          — 幾何計算ユーティリティ (点と線分の距離、座標一致判定)
tests/
  __init__.py
  test_models.py       — dataclass生成テスト
  test_geometry.py     — 幾何計算テスト
  test_parser.py       — パーサーの統合テスト(実DXF使用)
  test_checks.py       — チェックロジックの単体テスト(モックデータ)
  test_pn_numbering.py — P-N番号紐付けロジックの検証(実DXF使用)
app.py                 — Streamlit UI
requirements.txt       — 依存パッケージ
```

---

### Task 1: プロジェクトセットアップ

**Files:**
- Create: `requirements.txt`
- Create: `sleeve_checker/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: requirements.txt作成**

```
ezdxf>=1.0
streamlit>=1.30
matplotlib>=3.8
pytest>=8.0
```

- [ ] **Step 2: パッケージ初期化ファイル作成**

`sleeve_checker/__init__.py` と `tests/__init__.py` は空ファイル。

- [ ] **Step 3: 依存インストール**

Run: `pip install -r requirements.txt`

- [ ] **Step 4: コミット**

```bash
git add requirements.txt sleeve_checker/__init__.py tests/__init__.py
git commit -m "chore: project setup with dependencies"
```

---

### Task 2: データモデル (models.py)

**Files:**
- Create: `sleeve_checker/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: テスト作成**

```python
# tests/test_models.py
from sleeve_checker.models import (
    Sleeve, GridLine, DimLine, WallLine, StepLine, ColumnLine, FloorData, CheckResult
)

def test_sleeve_creation():
    s = Sleeve(
        id="スリーブ(S)-Z78Q3",
        center=(13180.0, 27750.0),
        diameter=175.0,
        label_text="KD φ175",
        fl_text="FL-710",
        pn_number="P-N-85",
        layer="[衛生]スリーブ",
        discipline="衛生",
    )
    assert s.diameter == 175.0
    assert s.discipline == "衛生"

def test_grid_line_creation():
    g = GridLine(axis_label="1", direction="V", position=0.0)
    assert g.direction == "V"

def test_floor_data_creation():
    fd = FloorData(
        sleeves=[], grid_lines=[], dim_lines=[],
        wall_lines=[], step_lines=[], column_lines=[],
        slab_level=None,
    )
    assert fd.sleeves == []

def test_check_result_creation():
    cr = CheckResult(
        check_id=3,
        check_name="口径・外径記載",
        severity="NG",
        sleeve=None,
        message="φ記載なし",
        related_coords=[],
    )
    assert cr.severity == "NG"
```

- [ ] **Step 2: テスト実行 → FAIL確認**

Run: `python -m pytest tests/test_models.py -v`
Expected: ImportError

- [ ] **Step 3: models.py実装**

```python
# sleeve_checker/models.py
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Sleeve:
    id: str
    center: tuple[float, float]
    diameter: float
    label_text: str | None = None
    fl_text: str | None = None
    pn_number: str | None = None
    layer: str = ""
    discipline: str = ""

@dataclass
class GridLine:
    axis_label: str
    direction: str  # "H" or "V"
    position: float

@dataclass
class DimLine:
    layer: str
    measurement: float
    defpoint1: tuple[float, float]
    defpoint2: tuple[float, float]
    text_override: str | None = None

@dataclass
class WallLine:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str = ""
    wall_type: str = "不明"  # "RC"/"LGS"/"ALC"/"PCa"/"パネル"/"不明"

@dataclass
class StepLine:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str = ""

@dataclass
class ColumnLine:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str = ""

@dataclass
class FloorData:
    sleeves: list[Sleeve] = field(default_factory=list)
    grid_lines: list[GridLine] = field(default_factory=list)
    dim_lines: list[DimLine] = field(default_factory=list)
    wall_lines: list[WallLine] = field(default_factory=list)
    step_lines: list[StepLine] = field(default_factory=list)
    column_lines: list[ColumnLine] = field(default_factory=list)
    slab_level: str | None = None

@dataclass
class CheckResult:
    check_id: int
    check_name: str
    severity: str  # "NG" / "WARNING" / "OK"
    sleeve: Sleeve | None = None
    message: str = ""
    related_coords: list[tuple[float, float]] = field(default_factory=list)
```

- [ ] **Step 4: テスト実行 → PASS確認**

Run: `python -m pytest tests/test_models.py -v`
Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add sleeve_checker/models.py tests/test_models.py
git commit -m "feat: add data models for sleeve checker"
```

---

### Task 3: 幾何計算ユーティリティ (geometry.py)

**Files:**
- Create: `sleeve_checker/geometry.py`
- Create: `tests/test_geometry.py`

- [ ] **Step 1: テスト作成**

```python
# tests/test_geometry.py
import math
from sleeve_checker.geometry import point_to_segment_distance, points_match

def test_point_to_segment_perpendicular():
    # 点(5,5)から線分(0,0)-(10,0)への距離 = 5.0
    assert abs(point_to_segment_distance((5, 5), (0, 0), (10, 0)) - 5.0) < 0.001

def test_point_to_segment_endpoint():
    # 点(15,0)から線分(0,0)-(10,0)への距離 = 5.0
    assert abs(point_to_segment_distance((15, 0), (0, 0), (10, 0)) - 5.0) < 0.001

def test_point_to_segment_on_line():
    # 点(5,0)は線分上 → 距離0
    assert abs(point_to_segment_distance((5, 0), (0, 0), (10, 0))) < 0.001

def test_points_match_within_tolerance():
    assert points_match((100.0, 200.0), (103.0, 198.0), tolerance=5.0)

def test_points_match_outside_tolerance():
    assert not points_match((100.0, 200.0), (110.0, 200.0), tolerance=5.0)

def test_point_to_vertical_segment():
    # 点(5,5)から縦線(0,0)-(0,10)への距離 = 5.0
    assert abs(point_to_segment_distance((5, 5), (0, 0), (0, 10)) - 5.0) < 0.001
```

- [ ] **Step 2: テスト実行 → FAIL確認**

Run: `python -m pytest tests/test_geometry.py -v`

- [ ] **Step 3: geometry.py実装**

```python
# sleeve_checker/geometry.py
import math

def point_to_segment_distance(
    point: tuple[float, float],
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
) -> float:
    """点から線分への最短距離を計算する。"""
    px, py = point
    ax, ay = seg_start
    bx, by = seg_end
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)

def points_match(
    p1: tuple[float, float],
    p2: tuple[float, float],
    tolerance: float = 5.0,
) -> bool:
    """2点が許容差以内で一致するか判定する。"""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1]) <= tolerance

def point_on_any_segment(
    point: tuple[float, float],
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    tolerance: float = 5.0,
) -> bool:
    """点がいずれかの線分上にあるか判定する。"""
    return any(
        point_to_segment_distance(point, s, e) <= tolerance
        for s, e in segments
    )
```

- [ ] **Step 4: テスト実行 → PASS確認**

Run: `python -m pytest tests/test_geometry.py -v`
Expected: 6 passed

- [ ] **Step 5: コミット**

```bash
git add sleeve_checker/geometry.py tests/test_geometry.py
git commit -m "feat: add geometry utilities for distance calculations"
```

---

### Task 4: パーサー基盤 — レイヤー検索とスリーブ抽出 (parser.py)

**Files:**
- Create: `sleeve_checker/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: テスト作成（実DXFで統合テスト）**

```python
# tests/test_parser.py
import os
import pytest
from sleeve_checker.parser import parse_dxf

DXF_2F = os.path.join(os.path.dirname(__file__), "..", "dxf_output", "2階床スリーブ図.dxf")
DXF_1F = os.path.join(os.path.dirname(__file__), "..", "dxf_output", "1階床スリーブ図.dxf")

@pytest.fixture
def floor_2f():
    return parse_dxf(DXF_2F)

@pytest.fixture
def floor_1f():
    return parse_dxf(DXF_1F)

def test_parse_2f_sleeves(floor_2f):
    """2Fスリーブが100個以上抽出される"""
    assert len(floor_2f.sleeves) >= 100

def test_parse_2f_sleeve_has_diameter(floor_2f):
    """全スリーブにdiameterが設定されている"""
    for s in floor_2f.sleeves:
        assert s.diameter > 0, f"{s.id} has no diameter"

def test_parse_2f_sleeve_has_center(floor_2f):
    """スリーブ中心が建物範囲内"""
    for s in floor_2f.sleeves:
        assert -1000 < s.center[0] < 90000, f"{s.id} X out of range: {s.center[0]}"
        assert -1000 < s.center[1] < 40000, f"{s.id} Y out of range: {s.center[1]}"

def test_parse_2f_grid_lines(floor_2f):
    """通り芯が抽出される"""
    h_lines = [g for g in floor_2f.grid_lines if g.direction == "H"]
    v_lines = [g for g in floor_2f.grid_lines if g.direction == "V"]
    assert len(h_lines) >= 4  # A,B,C,D,E
    assert len(v_lines) >= 6  # 1-8

def test_parse_2f_grid_positions(floor_2f):
    """通り芯Y座標が既知の値と一致"""
    h_positions = sorted(g.position for g in floor_2f.grid_lines if g.direction == "H")
    expected = [0, 4000, 19200, 25200, 34000]
    for exp in expected:
        assert any(abs(p - exp) < 10 for p in h_positions), f"Y={exp} not found"

def test_parse_2f_wall_lines(floor_2f):
    """壁線が抽出される"""
    assert len(floor_2f.wall_lines) > 0

def test_parse_2f_step_lines(floor_2f):
    """段差線が抽出される"""
    assert len(floor_2f.step_lines) > 0

def test_parse_2f_dim_lines(floor_2f):
    """寸法線が抽出される"""
    assert len(floor_2f.dim_lines) > 0

def test_parse_1f_sleeves(floor_1f):
    """1Fスリーブが200個以上抽出される"""
    assert len(floor_1f.sleeves) >= 200

def test_parse_1f_wall_lines(floor_1f):
    """1F壁線が抽出される（#6下階壁干渉用）"""
    assert len(floor_1f.wall_lines) > 0
```

- [ ] **Step 2: テスト実行 → FAIL確認**

Run: `python -m pytest tests/test_parser.py -v`

- [ ] **Step 3: parser.py実装 — レイヤー検索ヘルパー**

```python
# sleeve_checker/parser.py
from __future__ import annotations
import ezdxf
from ezdxf.document import Drawing
from ezdxf.layouts import Modelspace
from sleeve_checker.models import (
    Sleeve, GridLine, DimLine, WallLine, StepLine, ColumnLine, FloorData,
)

def _find_layers(doc: Drawing, suffix: str) -> list[str]:
    """レイヤー名の後半部分で検索。接頭辞([空調]等)に依存しない。"""
    return [l.dxf.name for l in doc.layers if suffix in l.dxf.name]

def _find_layers_any(doc: Drawing, keywords: list[str]) -> list[str]:
    """いずれかのキーワードを含むレイヤーを検索。"""
    result = []
    for l in doc.layers:
        if any(kw in l.dxf.name for kw in keywords):
            result.append(l.dxf.name)
    return result

def _entities_on_layers(msp: Modelspace, layers: list[str], dxftype: str | None = None):
    """指定レイヤー上のエンティティを取得。"""
    for e in msp:
        if e.dxf.layer in layers:
            if dxftype is None or e.dxftype() == dxftype:
                yield e
```

- [ ] **Step 4: parser.py実装 — スリーブ抽出**

```python
# sleeve_checker/parser.py に追記

def _extract_sleeves(doc: Drawing, msp: Modelspace) -> list[Sleeve]:
    """スリーブINSERTを抽出し、ブロック内CIRCLEから径を取得。"""
    sleeve_layers = _find_layers(doc, "スリーブ")
    sleeves = []
    for e in _entities_on_layers(msp, sleeve_layers, "INSERT"):
        block_name = e.dxf.name
        if "スリーブ" not in block_name and "箱" not in block_name:
            continue
        # ブロック定義からCIRCLE半径を取得
        diameter = 0.0
        if block_name in doc.blocks:
            for be in doc.blocks[block_name]:
                if be.dxftype() == "CIRCLE":
                    diameter = be.dxf.radius * 2
                    break
        if diameter == 0:
            continue
        # 設備種別を接頭辞から判定
        layer = e.dxf.layer
        discipline = "不明"
        for prefix, disc in [("衛生", "衛生"), ("空調", "空調"), ("電気", "電気"), ("建築", "建築")]:
            if prefix in layer:
                discipline = disc
                break
        sleeves.append(Sleeve(
            id=block_name,
            center=(e.dxf.insert.x, e.dxf.insert.y),
            diameter=diameter,
            layer=layer,
            discipline=discipline,
        ))
    return sleeves
```

- [ ] **Step 5: parser.py実装 — 通り芯・壁・段差線・寸法線・柱線抽出**

```python
# sleeve_checker/parser.py に追記

def _extract_grid_lines(doc: Drawing, msp: Modelspace) -> list[GridLine]:
    """通り芯LINEを抽出し、H/V判別。"""
    grid_layers = _find_layers_any(doc, ["C131_通心", "C131_通芯"])
    grids = []
    seen = set()
    for e in _entities_on_layers(msp, grid_layers, "LINE"):
        dx = abs(e.dxf.end.x - e.dxf.start.x)
        dy = abs(e.dxf.end.y - e.dxf.start.y)
        if dx > dy * 5:  # horizontal
            pos = round(e.dxf.start.y)
            if pos not in seen and -10000 < pos < 50000:
                seen.add(pos)
                grids.append(GridLine(axis_label="", direction="H", position=float(pos)))
        elif dy > dx * 5:  # vertical
            pos = round(e.dxf.start.x)
            if pos not in seen and -10000 < pos < 90000:
                seen.add(pos)
                grids.append(GridLine(axis_label="", direction="V", position=float(pos)))
    return grids

def _extract_wall_lines(doc: Drawing, msp: Modelspace) -> list[WallLine]:
    """壁線を抽出。RC壁は外形線、その他は壁心。"""
    walls = []
    # RC壁外形線
    for e in _entities_on_layers(msp, _find_layers(doc, "F106_RC壁"), "LINE"):
        walls.append(WallLine(
            start=(e.dxf.start.x, e.dxf.start.y),
            end=(e.dxf.end.x, e.dxf.end.y),
            layer=e.dxf.layer, wall_type="RC",
        ))
    # 壁心（RC以外の壁）
    for e in _entities_on_layers(msp, _find_layers(doc, "C151_壁心"), "LINE"):
        walls.append(WallLine(
            start=(e.dxf.start.x, e.dxf.start.y),
            end=(e.dxf.end.x, e.dxf.end.y),
            layer=e.dxf.layer, wall_type="不明",
        ))
    # LGS壁
    for e in _entities_on_layers(msp, _find_layers(doc, "A441_壁"), "LINE"):
        walls.append(WallLine(
            start=(e.dxf.start.x, e.dxf.start.y),
            end=(e.dxf.end.x, e.dxf.end.y),
            layer=e.dxf.layer, wall_type="LGS",
        ))
    # ALC壁
    for e in _entities_on_layers(msp, _find_layers(doc, "A422_壁"), "LINE"):
        walls.append(WallLine(
            start=(e.dxf.start.x, e.dxf.start.y),
            end=(e.dxf.end.x, e.dxf.end.y),
            layer=e.dxf.layer, wall_type="ALC",
        ))
    return walls

def _extract_step_lines(doc: Drawing, msp: Modelspace) -> list[StepLine]:
    """段差線・ヌスミ線を抽出。"""
    layers = _find_layers_any(doc, ["F108_3_RCスラブ段差線", "F108_5_床ヌスミ"])
    return [
        StepLine(
            start=(e.dxf.start.x, e.dxf.start.y),
            end=(e.dxf.end.x, e.dxf.end.y),
            layer=e.dxf.layer,
        )
        for e in _entities_on_layers(msp, layers, "LINE")
    ]

def _extract_column_lines(doc: Drawing, msp: Modelspace) -> list[ColumnLine]:
    """柱外形・壁仕上げ線を抽出（#12チェック用）。"""
    layers = _find_layers_any(doc, ["F102_RC柱", "F201_Ｓ柱", "A521_壁：仕上", "A422_壁：ＡＬＣ"])
    return [
        ColumnLine(
            start=(e.dxf.start.x, e.dxf.start.y),
            end=(e.dxf.end.x, e.dxf.end.y),
            layer=e.dxf.layer,
        )
        for e in _entities_on_layers(msp, layers, "LINE")
    ]

def _extract_dim_lines(doc: Drawing, msp: Modelspace) -> list[DimLine]:
    """全DIMENSIONエンティティを抽出。"""
    dims = []
    for e in msp:
        if e.dxftype() == "DIMENSION":
            try:
                dims.append(DimLine(
                    layer=e.dxf.layer,
                    measurement=e.dxf.get("actual_measurement", 0.0),
                    defpoint1=(e.dxf.defpoint.x, e.dxf.defpoint.y),
                    defpoint2=(e.dxf.defpoint2.x, e.dxf.defpoint2.y) if hasattr(e.dxf, "defpoint2") else (e.dxf.defpoint.x, e.dxf.defpoint.y),
                    text_override=e.dxf.get("text", None),
                ))
            except Exception:
                pass
    return dims
```

- [ ] **Step 6: parser.py実装 — テキスト紐付け**

```python
# sleeve_checker/parser.py に追記
import math

def _attach_label_texts(sleeves: list[Sleeve], doc: Drawing, msp: Modelspace) -> None:
    """スリーブに最近傍のラベルテキストとFLテキストを紐付ける。"""
    sleeve_layers = _find_layers(doc, "スリーブ")
    texts = []
    for e in _entities_on_layers(msp, sleeve_layers, "TEXT"):
        texts.append((e.dxf.insert.x, e.dxf.insert.y, e.dxf.text.strip()))

    for s in sleeves:
        best_label = None
        best_fl = None
        best_label_dist = float("inf")
        best_fl_dist = float("inf")
        for tx, ty, tt in texts:
            dist = math.hypot(tx - s.center[0], ty - s.center[1])
            if dist > 1500:
                continue
            if "FL" in tt.upper() or "fl" in tt.lower():
                if dist < best_fl_dist:
                    best_fl_dist = dist
                    best_fl = tt
            elif "φ" in tt or "Φ" in tt or "ø" in tt:
                if dist < best_label_dist:
                    best_label_dist = dist
                    best_label = tt
        s.label_text = best_label
        s.fl_text = best_fl
```

- [ ] **Step 7: parser.py実装 — parse_dxf メイン関数**

```python
# sleeve_checker/parser.py に追記

def _extract_slab_level(doc: Drawing, msp: Modelspace) -> str | None:
    """スラブレベルテキストを抽出。"""
    layers = _find_layers_any(doc, ["F308_スラブ", "スラブラベル"])
    for e in _entities_on_layers(msp, layers, "TEXT"):
        text = e.dxf.text.strip()
        if "スラブ" in text and "FL" in text:
            return text
    return None

def parse_dxf(filepath: str) -> FloorData:
    """DXFファイルをパースしてFloorDataを返す。"""
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()

    sleeves = _extract_sleeves(doc, msp)
    _attach_label_texts(sleeves, doc, msp)

    return FloorData(
        sleeves=sleeves,
        grid_lines=_extract_grid_lines(doc, msp),
        dim_lines=_extract_dim_lines(doc, msp),
        wall_lines=_extract_wall_lines(doc, msp),
        step_lines=_extract_step_lines(doc, msp),
        column_lines=_extract_column_lines(doc, msp),
        slab_level=_extract_slab_level(doc, msp),
    )
```

- [ ] **Step 8: テスト実行 → PASS確認**

Run: `python -m pytest tests/test_parser.py -v`
Expected: 全テストPASS

- [ ] **Step 9: コミット**

```bash
git add sleeve_checker/parser.py tests/test_parser.py
git commit -m "feat: implement DXF parser with sleeve/grid/wall/dim extraction"
```

---

### Task 5: P-N番号自動紐付け

**Files:**
- Modify: `sleeve_checker/parser.py`
- Create: `tests/test_pn_numbering.py`

- [ ] **Step 1: 検証テスト作成（実DXFでソート結果を出力して目視確認）**

```python
# tests/test_pn_numbering.py
import os
import pytest
from sleeve_checker.parser import parse_dxf, assign_pn_numbers

DXF_2F = os.path.join(os.path.dirname(__file__), "..", "dxf_output", "2階床スリーブ図.dxf")

@pytest.fixture
def floor_2f():
    return parse_dxf(DXF_2F)

def test_pn_assignment_count(floor_2f):
    """P-N番号が割り当てられたスリーブ数を確認"""
    assign_pn_numbers(floor_2f)
    assigned = [s for s in floor_2f.sleeves if s.pn_number is not None]
    # 2FにはP-N 97個が存在
    assert len(assigned) >= 90, f"Only {len(assigned)} sleeves got P-N numbers"

def test_pn_assignment_print(floor_2f):
    """割り当て結果を出力して目視確認用（常にpass、出力で確認）"""
    assign_pn_numbers(floor_2f)
    assigned = [(s.pn_number, s.center, s.label_text) for s in floor_2f.sleeves if s.pn_number]
    assigned.sort(key=lambda x: int(x[0].replace("P-N-", "")) if x[0] else 0)
    for pn, center, label in assigned:
        print(f"  {pn:>8} ({center[0]:>8.0f},{center[1]:>8.0f}) {label or ''}")
    assert True  # 目視確認用
```

- [ ] **Step 2: テスト実行 → FAIL確認（assign_pn_numbers未定義）**

Run: `python -m pytest tests/test_pn_numbering.py -v`

- [ ] **Step 3: P-N紐付けロジック実装**

```python
# sleeve_checker/parser.py に追記
import re

def assign_pn_numbers(floor_data: FloorData, doc=None, msp=None, filepath: str | None = None) -> None:
    """P-N番号をゾーンソートロジックでスリーブに紐付ける。

    filepathが指定された場合はDXFからP-Nテキストを読み直す。
    """
    # DXFからP-Nテキスト座標を取得
    if filepath:
        _doc = ezdxf.readfile(filepath)
        _msp = _doc.modelspace()
    elif doc and msp:
        _doc, _msp = doc, msp
    else:
        return

    pn_texts = []
    for e in _msp:
        if e.dxftype() == "TEXT" and "P-N-" in e.dxf.text:
            match = re.search(r"P-N-(\d+)", e.dxf.text)
            if match:
                pn_texts.append((
                    int(match.group(1)),
                    e.dxf.text.strip(),
                    e.dxf.insert.x,
                    e.dxf.insert.y,
                ))
    pn_texts.sort(key=lambda x: x[0])

    # 通り芯からグリッドゾーン定義
    h_positions = sorted(set(
        g.position for g in floor_data.grid_lines if g.direction == "H"
    ))
    v_positions = sorted(set(
        g.position for g in floor_data.grid_lines if g.direction == "V"
    ))

    # スリーブをゾーンソート
    sorted_sleeves = _zone_sort_sleeves(floor_data.sleeves, h_positions, v_positions)

    # P-N番号をソート順で割り当て
    for i, sleeve in enumerate(sorted_sleeves):
        if i < len(pn_texts):
            sleeve.pn_number = pn_texts[i][1]


def _zone_sort_sleeves(
    sleeves: list[Sleeve],
    h_bounds: list[float],
    v_bounds: list[float],
) -> list[Sleeve]:
    """スリーブをゾーン→縦列/横一列の規則でソートする。

    規則:
    1. グリッドゾーンを右上→左下順
    2. ゾーン内でY範囲を上→下
    3. 同Y範囲内の縦列は右→左、各縦列内は上→下
    4. 横一列は左→右
    """
    # 建物範囲外を除外（詳細図エリア等）
    building_sleeves = [
        s for s in sleeves
        if -1000 < s.center[0] < 90000 and -1000 < s.center[1] < 40000
    ]

    # ゾーン割り当て
    def get_zone(s: Sleeve) -> tuple[int, int]:
        vz = len(v_bounds)  # default: rightmost
        for i in range(len(v_bounds) - 1):
            if v_bounds[i] - 100 <= s.center[0] <= v_bounds[i + 1] + 100:
                vz = i
                break
        hz = len(h_bounds)
        for i in range(len(h_bounds) - 1):
            if h_bounds[i] - 100 <= s.center[1] <= h_bounds[i + 1] + 100:
                hz = i
                break
        return (vz, hz)

    # ゾーンごとにグルーピング
    from collections import defaultdict
    zones = defaultdict(list)
    for s in building_sleeves:
        zones[get_zone(s)].append(s)

    # ゾーンソート: X降順（右→左）, Y降順（上→下）
    sorted_zone_keys = sorted(zones.keys(), key=lambda z: (-z[1], -z[0]))

    result = []
    for zk in sorted_zone_keys:
        zone_sleeves = zones[zk]
        result.extend(_sort_within_zone(zone_sleeves))

    return result


def _sort_within_zone(sleeves: list[Sleeve]) -> list[Sleeve]:
    """ゾーン内をY範囲→縦列/横一列でソートする。"""
    if not sleeves:
        return []

    # X座標でグルーピング（差300mm以内は同じ縦列）
    sorted_by_x = sorted(sleeves, key=lambda s: s.center[0])
    columns: list[list[Sleeve]] = []
    current_col = [sorted_by_x[0]]
    for s in sorted_by_x[1:]:
        if abs(s.center[0] - current_col[-1].center[0]) < 300:
            current_col.append(s)
        else:
            columns.append(current_col)
            current_col = [s]
    columns.append(current_col)

    # 縦列（2個以上）と孤立（1個）に分離
    vertical_cols = [c for c in columns if len(c) >= 2]
    isolated = [c[0] for c in columns if len(c) == 1]

    result = []

    # Y範囲を上から下に処理
    all_y = [s.center[1] for s in sleeves]
    y_max, y_min = max(all_y), min(all_y)

    # 縦列を右→左でソートし、各縦列内を上→下(Y降順)
    vertical_cols.sort(key=lambda c: -max(s.center[0] for s in c))
    for col in vertical_cols:
        col.sort(key=lambda s: -s.center[1])
        result.extend(col)

    # 孤立スリーブ（横一列）は左→右
    isolated.sort(key=lambda s: s.center[0])
    result.extend(isolated)

    return result
```

- [ ] **Step 4: テスト実行 → 出力を目視確認**

Run: `python -m pytest tests/test_pn_numbering.py -v -s`
Expected: 出力されたP-N番号と座標を目視で確認。ユーザーと一緒にロジックを調整する。

- [ ] **Step 5: コミット**

```bash
git add sleeve_checker/parser.py tests/test_pn_numbering.py
git commit -m "feat: implement P-N numbering with zone-sort logic (initial)"
```

**Note:** このタスクは実データで検証→ロジック修正の反復が必要。初回実装後にユーザーと結果を確認し、`_sort_within_zone`を調整する。

---

### Task 6: チェックロジック — テキスト系 (#2, #3, #5, #8, #14)

**Files:**
- Create: `sleeve_checker/checks.py`
- Create: `tests/test_checks.py`

- [ ] **Step 1: テスト作成**

```python
# tests/test_checks.py
import pytest
from sleeve_checker.models import Sleeve, GridLine, DimLine, WallLine, StepLine, ColumnLine, FloorData, CheckResult
from sleeve_checker.checks import (
    check_discipline, check_diameter_label, check_gradient,
    check_fl_label, check_sleeve_number,
)

def _make_sleeve(**kwargs) -> Sleeve:
    defaults = dict(id="test", center=(0, 0), diameter=100, layer="[衛生]スリーブ", discipline="衛生")
    defaults.update(kwargs)
    return Sleeve(**defaults)

# #2 用途・設備種別
def test_check_discipline_ok():
    s = _make_sleeve(label_text="CW φ75")
    results = check_discipline(s)
    assert all(r.severity == "OK" for r in results)

def test_check_discipline_ng_no_label():
    s = _make_sleeve(label_text=None)
    results = check_discipline(s)
    assert any(r.severity == "NG" for r in results)

# #3 口径・外径記載
def test_check_diameter_label_ok():
    s = _make_sleeve(label_text="125φ(外径140φ)50A")
    results = check_diameter_label(s)
    assert all(r.severity == "OK" for r in results)

def test_check_diameter_label_ok_format2():
    s = _make_sleeve(label_text="CW φ75")
    results = check_diameter_label(s)
    assert all(r.severity == "OK" for r in results)

def test_check_diameter_label_ng():
    s = _make_sleeve(label_text="CW")
    results = check_diameter_label(s)
    assert any(r.severity == "NG" for r in results)

# #5 勾配確保
def test_check_gradient_ok_not_drain():
    s = _make_sleeve(label_text="CW φ75")
    results = check_gradient(s)
    assert all(r.severity == "OK" for r in results)

def test_check_gradient_warning_drain_no_fl():
    s = _make_sleeve(label_text="SD φ225", fl_text=None)
    results = check_gradient(s)
    assert any(r.severity == "WARNING" for r in results)

def test_check_gradient_ok_drain_with_fl():
    s = _make_sleeve(label_text="SD φ225", fl_text="FL-710")
    results = check_gradient(s)
    assert all(r.severity == "OK" for r in results)

# #8 基準レベル記載
def test_check_fl_label_ok():
    s = _make_sleeve(fl_text="FL-710")
    results = check_fl_label(s)
    assert all(r.severity == "OK" for r in results)

def test_check_fl_label_ng():
    s = _make_sleeve(fl_text=None)
    results = check_fl_label(s)
    assert any(r.severity == "NG" for r in results)

# #14 スリーブNo
def test_check_sleeve_number_ok():
    s = _make_sleeve(pn_number="P-N-1")
    results = check_sleeve_number(s)
    assert all(r.severity == "OK" for r in results)

def test_check_sleeve_number_ng():
    s = _make_sleeve(pn_number=None)
    results = check_sleeve_number(s)
    assert any(r.severity == "NG" for r in results)
```

- [ ] **Step 2: テスト実行 → FAIL確認**

Run: `python -m pytest tests/test_checks.py -v`

- [ ] **Step 3: チェック関数実装**

```python
# sleeve_checker/checks.py
from __future__ import annotations
import re
from sleeve_checker.models import Sleeve, FloorData, CheckResult

DRAIN_CODES = ["SD", "RD", "WD", "排水", "汚水", "雨水"]

def check_discipline(sleeve: Sleeve) -> list[CheckResult]:
    """#2: 用途・設備種別を記載したか"""
    if sleeve.label_text and len(sleeve.label_text.strip()) > 0:
        return [CheckResult(2, "用途・設備種別", "OK", sleeve, "種別記載あり")]
    return [CheckResult(2, "用途・設備種別", "NG", sleeve, "種別記載なし",
                        related_coords=[sleeve.center])]

def check_diameter_label(sleeve: Sleeve) -> list[CheckResult]:
    """#3: 口径・外径記載"""
    if sleeve.label_text and re.search(r"[φΦø]\s*\d+|\d+\s*[φΦø]", sleeve.label_text):
        return [CheckResult(3, "口径・外径記載", "OK", sleeve, "径記載あり")]
    return [CheckResult(3, "口径・外径記載", "NG", sleeve, "φ記載なし",
                        related_coords=[sleeve.center])]

def check_gradient(sleeve: Sleeve) -> list[CheckResult]:
    """#5: 勾配確保（排水系のみ）"""
    is_drain = sleeve.label_text and any(c in sleeve.label_text for c in DRAIN_CODES)
    if not is_drain:
        return [CheckResult(5, "勾配確保", "OK", sleeve, "排水系でない")]
    if sleeve.fl_text and re.search(r"FL|1/\d+", sleeve.fl_text):
        return [CheckResult(5, "勾配確保", "OK", sleeve, "FL/勾配記載あり")]
    return [CheckResult(5, "勾配確保", "WARNING", sleeve, "排水スリーブにFL/勾配記載なし",
                        related_coords=[sleeve.center])]

def check_fl_label(sleeve: Sleeve) -> list[CheckResult]:
    """#8: 基準レベル記載"""
    if sleeve.fl_text and re.search(r"FL\s*[±+\-]\s*\d+", sleeve.fl_text):
        return [CheckResult(8, "基準レベル記載", "OK", sleeve, "FL記載あり")]
    return [CheckResult(8, "基準レベル記載", "NG", sleeve, "FL記載なし",
                        related_coords=[sleeve.center])]

def check_sleeve_number(sleeve: Sleeve) -> list[CheckResult]:
    """#14: スリーブNo記載"""
    if sleeve.pn_number and re.search(r"P-N-\d+", sleeve.pn_number):
        return [CheckResult(14, "スリーブNo", "OK", sleeve, f"{sleeve.pn_number}")]
    return [CheckResult(14, "スリーブNo", "NG", sleeve, "P-N番号なし",
                        related_coords=[sleeve.center])]
```

- [ ] **Step 4: テスト実行 → PASS確認**

Run: `python -m pytest tests/test_checks.py -v`
Expected: 12 passed

- [ ] **Step 5: コミット**

```bash
git add sleeve_checker/checks.py tests/test_checks.py
git commit -m "feat: implement text-based checks (#2,#3,#5,#8,#14)"
```

---

### Task 7: チェックロジック — 幾何系 (#6, #7, #10, #11, #12)

**Files:**
- Modify: `sleeve_checker/checks.py`
- Modify: `tests/test_checks.py`

- [ ] **Step 1: テスト追加**

```python
# tests/test_checks.py に追記
from sleeve_checker.checks import (
    check_lower_wall, check_step_slab, check_step_dim,
    check_sleeve_center_dim, check_column_wall_dim,
)
from sleeve_checker.models import DimLine, WallLine, StepLine, ColumnLine

# #6 下階壁干渉
def test_check_lower_wall_ng():
    sleeve = _make_sleeve(center=(1000, 1000), diameter=200)
    walls = [WallLine(start=(1000, 0), end=(1000, 2000), wall_type="不明")]
    results = check_lower_wall(sleeve, walls, {"不明": 200.0})
    assert any(r.severity == "NG" for r in results)

def test_check_lower_wall_ok():
    sleeve = _make_sleeve(center=(5000, 1000), diameter=200)
    walls = [WallLine(start=(1000, 0), end=(1000, 2000), wall_type="不明")]
    results = check_lower_wall(sleeve, walls, {"不明": 200.0})
    assert all(r.severity == "OK" for r in results)

# #7 段差スラブ
def test_check_step_slab_warning():
    sleeve = _make_sleeve(center=(100, 500))
    steps = [StepLine(start=(0, 0), end=(0, 1000))]
    results = check_step_slab(sleeve, steps, threshold=200.0)
    assert any(r.severity == "WARNING" for r in results)

def test_check_step_slab_ok():
    sleeve = _make_sleeve(center=(500, 500))
    steps = [StepLine(start=(0, 0), end=(0, 1000))]
    results = check_step_slab(sleeve, steps, threshold=200.0)
    assert all(r.severity == "OK" for r in results)

# #10 型枠段差寄り
def test_check_step_dim_ng():
    dim = DimLine(layer="test", measurement=300, defpoint1=(0, 500), defpoint2=(300, 500))
    steps = [StepLine(start=(0, 0), end=(0, 1000))]
    results = check_step_dim(dim, steps)
    assert any(r.severity == "NG" for r in results)

def test_check_step_dim_ok():
    dim = DimLine(layer="test", measurement=300, defpoint1=(500, 500), defpoint2=(800, 500))
    steps = [StepLine(start=(0, 0), end=(0, 1000))]
    results = check_step_dim(dim, steps)
    assert all(r.severity == "OK" for r in results)

# #11 スリーブ芯寄り
def test_check_sleeve_center_dim_ng():
    s1 = _make_sleeve(id="s1", center=(1000, 1000))
    s2 = _make_sleeve(id="s2", center=(1300, 1000))
    dim = DimLine(layer="test", measurement=300, defpoint1=(1000, 1000), defpoint2=(1300, 1000))
    results = check_sleeve_center_dim(dim, [s1, s2])
    assert any(r.severity == "NG" for r in results)

def test_check_sleeve_center_dim_ok():
    s1 = _make_sleeve(id="s1", center=(1000, 1000))
    dim = DimLine(layer="test", measurement=1000, defpoint1=(0, 1000), defpoint2=(1000, 1000))
    results = check_sleeve_center_dim(dim, [s1])
    assert all(r.severity == "OK" for r in results)

# #12 柱面・仕上面寄り
def test_check_column_wall_dim_ng():
    dim = DimLine(layer="test", measurement=300, defpoint1=(100, 500), defpoint2=(400, 500))
    cols = [ColumnLine(start=(100, 0), end=(100, 1000))]
    results = check_column_wall_dim(dim, cols)
    assert any(r.severity == "NG" for r in results)
```

- [ ] **Step 2: テスト実行 → FAIL確認**

Run: `python -m pytest tests/test_checks.py -v`

- [ ] **Step 3: 幾何チェック実装**

```python
# sleeve_checker/checks.py に追記
from sleeve_checker.geometry import point_to_segment_distance, points_match, point_on_any_segment
from sleeve_checker.models import DimLine, WallLine, StepLine, ColumnLine

COORD_TOLERANCE = 5.0

def check_lower_wall(
    sleeve: Sleeve,
    lower_walls: list[WallLine],
    wall_thickness: dict[str, float],
) -> list[CheckResult]:
    """#6: 下階壁干渉"""
    for w in lower_walls:
        dist = point_to_segment_distance(sleeve.center, w.start, w.end)
        if w.wall_type == "RC":
            threshold = sleeve.diameter / 2
        else:
            half_wall = wall_thickness.get(w.wall_type, 200.0) / 2
            threshold = sleeve.diameter / 2 + half_wall
        if dist < threshold:
            return [CheckResult(6, "下階壁干渉", "NG", sleeve,
                                f"壁({w.wall_type})と干渉 距離{dist:.0f}mm",
                                related_coords=[sleeve.center, w.start, w.end])]
    return [CheckResult(6, "下階壁干渉", "OK", sleeve, "干渉なし")]

def check_step_slab(
    sleeve: Sleeve,
    step_lines: list[StepLine],
    threshold: float | None = None,
) -> list[CheckResult]:
    """#7: 段差スラブ施工不可"""
    if threshold is None:
        return [CheckResult(7, "段差スラブ", "OK", sleeve, "しきい値未設定（スキップ）")]
    for st in step_lines:
        dist = point_to_segment_distance(sleeve.center, st.start, st.end)
        if dist < threshold:
            return [CheckResult(7, "段差スラブ", "WARNING", sleeve,
                                f"段差線から{dist:.0f}mm（しきい値{threshold:.0f}mm）",
                                related_coords=[sleeve.center, st.start, st.end])]
    return [CheckResult(7, "段差スラブ", "OK", sleeve, "段差線から十分離れている")]

def check_step_dim(
    dim: DimLine,
    step_lines: list[StepLine],
    tolerance: float = COORD_TOLERANCE,
) -> list[CheckResult]:
    """#10: 型枠段差からの寄り寸法"""
    segments = [(s.start, s.end) for s in step_lines]
    if point_on_any_segment(dim.defpoint1, segments, tolerance):
        return [CheckResult(10, "型枠段差寄り", "NG", None,
                            f"寸法起点が段差線上",
                            related_coords=[dim.defpoint1])]
    return [CheckResult(10, "型枠段差寄り", "OK")]

def check_sleeve_center_dim(
    dim: DimLine,
    sleeves: list[Sleeve],
    tolerance: float = COORD_TOLERANCE,
) -> list[CheckResult]:
    """#11: スリーブ芯からの寄り寸法"""
    p1_on_sleeve = any(points_match(dim.defpoint1, s.center, tolerance) for s in sleeves)
    p2_on_sleeve = any(points_match(dim.defpoint2, s.center, tolerance) for s in sleeves)
    if p1_on_sleeve and p2_on_sleeve:
        return [CheckResult(11, "スリーブ芯寄り", "NG", None,
                            "寸法がスリーブ間で取られている",
                            related_coords=[dim.defpoint1, dim.defpoint2])]
    return [CheckResult(11, "スリーブ芯寄り", "OK")]

def check_column_wall_dim(
    dim: DimLine,
    column_lines: list[ColumnLine],
    tolerance: float = COORD_TOLERANCE,
) -> list[CheckResult]:
    """#12: 柱面・仕上面からの寄り寸法"""
    segments = [(c.start, c.end) for c in column_lines]
    if point_on_any_segment(dim.defpoint1, segments, tolerance):
        return [CheckResult(12, "柱面・仕上面寄り", "NG", None,
                            "寸法起点が柱面/壁仕上面上",
                            related_coords=[dim.defpoint1])]
    return [CheckResult(12, "柱面・仕上面寄り", "OK")]
```

- [ ] **Step 4: テスト実行 → PASS確認**

Run: `python -m pytest tests/test_checks.py -v`
Expected: 全テストPASS

- [ ] **Step 5: コミット**

```bash
git add sleeve_checker/checks.py tests/test_checks.py
git commit -m "feat: implement geometry-based checks (#6,#7,#10,#11,#12)"
```

---

### Task 8: チェックロジック — 寸法系 (#4, #9, #13)

**Files:**
- Modify: `sleeve_checker/checks.py`
- Modify: `tests/test_checks.py`

- [ ] **Step 1: テスト追加**

```python
# tests/test_checks.py に追記
from sleeve_checker.checks import check_dim_sum, check_both_sides, check_dim_notation

# #4 寸法合計一致
def test_check_dim_sum_ok():
    grids = [
        GridLine("1", "V", 0.0),
        GridLine("2", "V", 10000.0),
    ]
    dims = [
        DimLine("test", 3000, (0, 100), (3000, 100)),
        DimLine("test", 4000, (3000, 100), (7000, 100)),
        DimLine("test", 3000, (7000, 100), (10000, 100)),
    ]
    results = check_dim_sum(dims, grids)
    assert all(r.severity == "OK" for r in results)

def test_check_dim_sum_ng():
    grids = [
        GridLine("1", "V", 0.0),
        GridLine("2", "V", 10000.0),
    ]
    dims = [
        DimLine("test", 3000, (0, 100), (3000, 100)),
        DimLine("test", 4000, (3000, 100), (7000, 100)),
        # missing 3000 → sum = 7000 ≠ 10000
    ]
    results = check_dim_sum(dims, grids)
    assert any(r.severity == "NG" for r in results)

# #9 片側基準のみ
def test_check_both_sides_ok():
    sleeve = _make_sleeve(center=(5000, 5000))
    grids = [GridLine("1", "V", 0.0), GridLine("2", "V", 10000.0),
             GridLine("A", "H", 0.0), GridLine("B", "H", 10000.0)]
    dims = [
        DimLine("test", 5000, (0, 5000), (5000, 5000)),
        DimLine("test", 5000, (10000, 5000), (5000, 5000)),
        DimLine("test", 5000, (5000, 0), (5000, 5000)),
        DimLine("test", 5000, (5000, 10000), (5000, 5000)),
    ]
    results = check_both_sides(sleeve, dims, grids)
    assert all(r.severity == "OK" for r in results)

# #13 表記統一性
def test_check_dim_notation_ok():
    dims = [
        DimLine("test", 300, (0, 0), (300, 0), text_override=None),
        DimLine("test", 500, (0, 0), (500, 0), text_override=None),
    ]
    results = check_dim_notation(dims)
    assert all(r.severity == "OK" for r in results)
```

- [ ] **Step 2: テスト実行 → FAIL確認**

Run: `python -m pytest tests/test_checks.py -v`

- [ ] **Step 3: 寸法チェック実装**

```python
# sleeve_checker/checks.py に追記
from sleeve_checker.models import GridLine

DIM_SUM_TOLERANCE = 1.0

def check_dim_sum(dims: list[DimLine], grids: list[GridLine]) -> list[CheckResult]:
    """#4: 通り芯間寸法合計一致"""
    results = []
    v_grids = sorted([g for g in grids if g.direction == "V"], key=lambda g: g.position)
    for i in range(len(v_grids) - 1):
        x1 = v_grids[i].position
        x2 = v_grids[i + 1].position
        span = x2 - x1
        # この通り芯間にあるX方向寸法を集める
        between = [d for d in dims
                   if min(d.defpoint1[0], d.defpoint2[0]) >= x1 - 10
                   and max(d.defpoint1[0], d.defpoint2[0]) <= x2 + 10
                   and abs(d.defpoint1[1] - d.defpoint2[1]) < 100]  # ほぼ水平
        if between:
            total = sum(d.measurement for d in between)
            if abs(total - span) > DIM_SUM_TOLERANCE:
                results.append(CheckResult(4, "寸法合計一致", "NG", None,
                    f"通り芯{v_grids[i].axis_label}-{v_grids[i+1].axis_label}間: "
                    f"寸法合計{total:.0f} ≠ 通り芯間{span:.0f}",
                    related_coords=[(x1, 0), (x2, 0)]))
    if not results:
        results.append(CheckResult(4, "寸法合計一致", "OK", None, "寸法合計一致"))
    return results

def check_both_sides(
    sleeve: Sleeve,
    dims: list[DimLine],
    grids: list[GridLine],
    tolerance: float = 100.0,
) -> list[CheckResult]:
    """#9: 片側基準のみでないか"""
    # スリーブ近傍の寸法線を探す
    nearby_dims = [d for d in dims
                   if points_match(d.defpoint1, sleeve.center, 1500)
                   or points_match(d.defpoint2, sleeve.center, 1500)]

    v_grids = [g.position for g in grids if g.direction == "V"]
    h_grids = [g.position for g in grids if g.direction == "H"]

    has_left = has_right = has_top = has_bottom = False
    sx, sy = sleeve.center

    for d in nearby_dims:
        for dp in [d.defpoint1, d.defpoint2]:
            if any(abs(dp[0] - g) < tolerance for g in v_grids):
                if dp[0] < sx:
                    has_left = True
                elif dp[0] > sx:
                    has_right = True
            if any(abs(dp[1] - g) < tolerance for g in h_grids):
                if dp[1] < sy:
                    has_bottom = True
                elif dp[1] > sy:
                    has_top = True

    issues = []
    if not (has_left and has_right):
        issues.append("X方向で片側のみ")
    if not (has_top and has_bottom):
        issues.append("Y方向で片側のみ")

    if issues:
        return [CheckResult(9, "片側基準のみ", "NG", sleeve,
                            "、".join(issues), related_coords=[sleeve.center])]
    return [CheckResult(9, "片側基準のみ", "OK", sleeve, "両側基準あり")]

def check_dim_notation(dims: list[DimLine]) -> list[CheckResult]:
    """#13: 寸法表記統一性"""
    overrides = [d.text_override for d in dims if d.text_override and d.text_override != "<>"]
    if not overrides:
        return [CheckResult(13, "表記統一性", "OK", None, "全て自動表記（統一）")]
    # パターン分類
    from collections import Counter
    patterns = Counter()
    for t in overrides:
        if "mm" in t:
            patterns["mm付き"] += 1
        elif "," in t:
            patterns["カンマ区切り"] += 1
        elif "." in t:
            patterns["小数あり"] += 1
        else:
            patterns["標準"] += 1

    if len(patterns) <= 1:
        return [CheckResult(13, "表記統一性", "OK", None, "表記統一")]

    majority = patterns.most_common(1)[0][0]
    outliers = [p for p in patterns if p != majority]
    return [CheckResult(13, "表記統一性", "WARNING", None,
                        f"多数派: {majority}, 逸脱: {', '.join(outliers)}")]
```

- [ ] **Step 4: テスト実行 → PASS確認**

Run: `python -m pytest tests/test_checks.py -v`

- [ ] **Step 5: コミット**

```bash
git add sleeve_checker/checks.py tests/test_checks.py
git commit -m "feat: implement dimension-based checks (#4,#9,#13)"
```

---

### Task 9: run_all_checks 統合関数

**Files:**
- Modify: `sleeve_checker/checks.py`

- [ ] **Step 1: run_all_checks実装**

```python
# sleeve_checker/checks.py に追記

def run_all_checks(
    floor_2f: FloorData,
    floor_1f: FloorData | None = None,
    wall_thickness: dict[str, float] | None = None,
    step_threshold: float | None = None,
) -> list[CheckResult]:
    """全チェックを実行してCheckResult一覧を返す。"""
    if wall_thickness is None:
        wall_thickness = {"RC": 0, "LGS": 150, "ALC": 150, "PCa": 200, "パネル": 100, "不明": 200}

    results = []

    # スリーブ単位チェック
    for s in floor_2f.sleeves:
        results.extend(check_discipline(s))       # #2
        results.extend(check_diameter_label(s))    # #3
        results.extend(check_gradient(s))          # #5
        results.extend(check_fl_label(s))          # #8
        results.extend(check_sleeve_number(s))     # #14
        results.extend(check_step_slab(s, floor_2f.step_lines, step_threshold))  # #7

        # #6 下階壁干渉
        if floor_1f:
            results.extend(check_lower_wall(s, floor_1f.wall_lines, wall_thickness))

    # 寸法単位チェック
    results.extend(check_dim_sum(floor_2f.dim_lines, floor_2f.grid_lines))  # #4
    results.extend(check_dim_notation(floor_2f.dim_lines))  # #13

    for d in floor_2f.dim_lines:
        results.extend(check_step_dim(d, floor_2f.step_lines))        # #10
        results.extend(check_sleeve_center_dim(d, floor_2f.sleeves))  # #11
        results.extend(check_column_wall_dim(d, floor_2f.column_lines))  # #12

    # #9 片側基準
    for s in floor_2f.sleeves:
        results.extend(check_both_sides(s, floor_2f.dim_lines, floor_2f.grid_lines))

    return results
```

- [ ] **Step 2: 実DXFで統合テスト実行**

```python
# tests/test_parser.py に追記
from sleeve_checker.checks import run_all_checks

def test_run_all_checks_2f(floor_2f):
    """2F単体で全チェック実行してクラッシュしない"""
    results = run_all_checks(floor_2f)
    assert len(results) > 0
    ng = [r for r in results if r.severity == "NG"]
    warn = [r for r in results if r.severity == "WARNING"]
    ok = [r for r in results if r.severity == "OK"]
    print(f"NG: {len(ng)}, WARNING: {len(warn)}, OK: {len(ok)}")

def test_run_all_checks_with_1f(floor_2f, floor_1f):
    """1F+2Fで#6含む全チェック実行"""
    results = run_all_checks(floor_2f, floor_1f)
    check6 = [r for r in results if r.check_id == 6]
    assert len(check6) > 0
    print(f"#6 下階壁干渉: NG={sum(1 for r in check6 if r.severity=='NG')}, OK={sum(1 for r in check6 if r.severity=='OK')}")
```

- [ ] **Step 3: テスト実行 → PASS確認**

Run: `python -m pytest tests/test_parser.py::test_run_all_checks_2f tests/test_parser.py::test_run_all_checks_with_1f -v -s`

- [ ] **Step 4: コミット**

```bash
git add sleeve_checker/checks.py tests/test_parser.py
git commit -m "feat: add run_all_checks integration function"
```

---

### Task 10: Streamlit UI (app.py)

**Files:**
- Create: `app.py`

- [ ] **Step 1: app.py実装**

```python
# app.py
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib
from sleeve_checker.parser import parse_dxf, assign_pn_numbers
from sleeve_checker.checks import run_all_checks
from sleeve_checker.models import CheckResult

matplotlib.rcParams["font.family"] = "MS Gothic"

st.set_page_config(page_title="スリーブチェッカー", layout="wide")
st.title("スリーブチェッカー")

# サイドバー: 設定
with st.sidebar:
    st.header("設定")
    st.subheader("壁厚仮定値 (mm)")
    wt_lgs = st.number_input("LGS壁", value=150, step=10)
    wt_alc = st.number_input("ALC壁", value=150, step=10)
    wt_pca = st.number_input("PCa壁", value=200, step=10)
    wt_panel = st.number_input("パネル壁", value=100, step=10)
    wt_unknown = st.number_input("不明", value=200, step=10)
    wall_thickness = {
        "RC": 0, "LGS": wt_lgs, "ALC": wt_alc,
        "PCa": wt_pca, "パネル": wt_panel, "不明": wt_unknown,
    }

    st.subheader("しきい値")
    step_threshold_input = st.number_input(
        "#7 段差スラブ (mm)", value=0, step=10,
        help="0の場合はチェックスキップ",
    )
    step_threshold = step_threshold_input if step_threshold_input > 0 else None

# ファイルアップロード
col1, col2 = st.columns(2)
with col1:
    file_2f = st.file_uploader("2F DXFファイル", type=["dxf"])
with col2:
    file_1f = st.file_uploader("1F DXFファイル（下階壁干渉用）", type=["dxf"])

if file_2f and st.button("チェック実行", type="primary"):
    # 一時ファイルに保存してパース
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp.write(file_2f.read())
        tmp_2f = tmp.name

    with st.spinner("2F DXF解析中..."):
        floor_2f = parse_dxf(tmp_2f)
        assign_pn_numbers(floor_2f, filepath=tmp_2f)

    floor_1f = None
    if file_1f:
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
            tmp.write(file_1f.read())
            tmp_1f = tmp.name
        with st.spinner("1F DXF解析中..."):
            floor_1f = parse_dxf(tmp_1f)

    with st.spinner("チェック実行中..."):
        results = run_all_checks(floor_2f, floor_1f, wall_thickness, step_threshold)

    # サマリ
    ng = [r for r in results if r.severity == "NG"]
    warn = [r for r in results if r.severity == "WARNING"]
    ok = [r for r in results if r.severity == "OK"]

    c1, c2, c3 = st.columns(3)
    c1.metric("NG", len(ng))
    c2.metric("WARNING", len(warn))
    c3.metric("OK", len(ok))

    # 図面ビュー
    st.subheader("図面ビュー")
    fig, ax = plt.subplots(1, 1, figsize=(16, 8))

    # 通り芯
    for g in floor_2f.grid_lines:
        if g.direction == "H":
            ax.axhline(y=g.position, color="lightgray", linewidth=0.5, linestyle="--")
        else:
            ax.axvline(x=g.position, color="lightgray", linewidth=0.5, linestyle="--")

    # 壁線
    for w in floor_2f.wall_lines:
        ax.plot([w.start[0], w.end[0]], [w.start[1], w.end[1]],
                color="gray", linewidth=0.3)

    # スリーブ判定結果でカラーリング
    sleeve_results = {}
    for r in results:
        if r.sleeve:
            sid = r.sleeve.id
            if sid not in sleeve_results or r.severity == "NG":
                sleeve_results[sid] = r.severity
            elif sleeve_results[sid] != "NG" and r.severity == "WARNING":
                sleeve_results[sid] = "WARNING"

    colors = {"NG": "red", "WARNING": "orange", "OK": "green"}
    for s in floor_2f.sleeves:
        color = colors.get(sleeve_results.get(s.id, "OK"), "green")
        circle = plt.Circle(s.center, s.diameter / 2, fill=False,
                            edgecolor=color, linewidth=1.5)
        ax.add_patch(circle)
        if s.pn_number:
            ax.annotate(s.pn_number, s.center, fontsize=4,
                        ha="center", va="bottom", color=color)

    ax.set_aspect("equal")
    ax.set_xlim(-5000, 85000)
    ax.set_ylim(-5000, 40000)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    st.pyplot(fig)

    # 一覧テーブル
    st.subheader("チェック結果一覧")
    filter_severity = st.selectbox("フィルタ", ["全て", "NG", "WARNING", "OK"])

    import pandas as pd
    rows = []
    for r in results:
        if filter_severity != "全て" and r.severity != filter_severity:
            continue
        rows.append({
            "チェック#": r.check_id,
            "チェック名": r.check_name,
            "結果": r.severity,
            "スリーブ": r.sleeve.pn_number or r.sleeve.id if r.sleeve else "-",
            "径": r.sleeve.diameter if r.sleeve else "-",
            "メッセージ": r.message,
        })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("該当なし")

    # cleanup
    os.unlink(tmp_2f)
    if file_1f:
        os.unlink(tmp_1f)
```

- [ ] **Step 2: 動作確認**

Run: `streamlit run app.py`
ブラウザでDXFをアップロードしてチェック結果が表示されることを確認。

- [ ] **Step 3: コミット**

```bash
git add app.py
git commit -m "feat: add Streamlit UI with drawing view and results table"
```

---

### Task 11: 統合テスト & 調整

- [ ] **Step 1: 全テスト実行**

Run: `python -m pytest tests/ -v`
Expected: 全テストPASS

- [ ] **Step 2: Streamlit UIで実DXF投入して結果確認**

Run: `streamlit run app.py`
2F DXFと1F DXFをアップロードし、以下を確認:
- スリーブが正しく抽出されている
- P-N番号が概ね正しく割り当てられている
- 図面ビューでNG/WARNING/OKの色分けが見える
- テーブルでフィルタが機能する

- [ ] **Step 3: P-N番号紐付けの調整**

ユーザーと結果を見比べ、`_sort_within_zone`のロジックを修正。

- [ ] **Step 4: 最終コミット**

```bash
git add -A
git commit -m "feat: sleeve checker v1 complete"
```
