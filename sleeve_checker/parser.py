"""
parser.py - DXF to FloorData parser.

This is the ONLY module that imports ezdxf. It reads a DXF file and converts
the relevant entities into the FloorData dataclass consumed by check logic.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import TYPE_CHECKING

import ezdxf

from .models import (
    ColumnLine,
    DimLine,
    FloorData,
    GridLine,
    Sleeve,
    StepLine,
    WallLine,
)

# ---------------------------------------------------------------------------
# Building coordinate range (mm).  Entities outside this box are detail
# drawings or construction notes and should be excluded from checks.
# ---------------------------------------------------------------------------
BLDG_X_MIN = 0.0
BLDG_X_MAX = 80_000.0
BLDG_Y_MIN = 0.0
BLDG_Y_MAX = 34_000.0

# Search radius (mm) for associating label / FL texts with sleeve centers.
_LABEL_SEARCH_RADIUS = 1_500.0

# ---------------------------------------------------------------------------
# Regex patterns used in text association
# ---------------------------------------------------------------------------
_RE_PHI = re.compile(r"[φΦ]|\d+\s*[φΦ]|[φΦ]\s*\d+|外径|\d+A\b", re.IGNORECASE)
_RE_FL = re.compile(r"FL\s*[+\-]\s*\d+", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Layer-lookup helpers
# ---------------------------------------------------------------------------

def _find_layers(doc: ezdxf.document.Drawing, suffix: str) -> list[str]:
    """Return all layer names whose name contains *suffix*."""
    return [
        layer.dxf.name
        for layer in doc.layers
        if suffix in layer.dxf.name
    ]


def _find_layers_any(doc: ezdxf.document.Drawing, keywords: list[str]) -> list[str]:
    """Return layer names that contain ANY of the given keywords."""
    result = []
    for layer in doc.layers:
        name = layer.dxf.name
        if any(kw in name for kw in keywords):
            result.append(name)
    return result


def _entities_on_layers(msp, layers: list[str], dxftype: str):
    """Yield entities of *dxftype* whose layer is in *layers* (set lookup)."""
    layer_set = set(layers)
    for entity in msp:
        if entity.dxftype() == dxftype and entity.dxf.layer in layer_set:
            yield entity


# ---------------------------------------------------------------------------
# Sleeve extraction
# ---------------------------------------------------------------------------

def _discipline_from_layer(layer_name: str) -> str:
    """Infer discipline (衛生/空調/電気/建築) from layer prefix."""
    for disc in ("衛生", "空調", "電気", "建築"):
        if disc in layer_name:
            return disc
    return ""


_BLDG_TOLERANCE = 10.0  # mm tolerance for floating-point at boundaries


def _in_building_range(x: float, y: float) -> bool:
    return (
        BLDG_X_MIN - _BLDG_TOLERANCE <= x <= BLDG_X_MAX + _BLDG_TOLERANCE
        and BLDG_Y_MIN - _BLDG_TOLERANCE <= y <= BLDG_Y_MAX + _BLDG_TOLERANCE
    )


def _get_block_circles(doc, block_name: str) -> list[tuple[float, float, float]]:
    """
    Return list of (offset_x, offset_y, diameter) for every CIRCLE in the
    named block definition.  Returns empty list if the block is not found.
    """
    block = doc.blocks.get(block_name)
    if block is None:
        return []
    circles = []
    for ent in block:
        if ent.dxftype() == "CIRCLE":
            cx = ent.dxf.center.x
            cy = ent.dxf.center.y
            d = ent.dxf.radius * 2.0
            circles.append((cx, cy, d))
    return circles


def _get_block_bbox_size(doc, block_name: str) -> tuple[float, float, float, float] | None:
    """
    For blocks with no CIRCLE (box / rectangular sleeves), estimate the
    sleeve size from the bounding box of all LINE and LWPOLYLINE endpoints.

    Returns (cx, cy, width, height) in block-local coordinates, or None if
    the block has no measurable geometry.
    """
    block = doc.blocks.get(block_name)
    if block is None:
        return None

    xs: list[float] = []
    ys: list[float] = []

    for ent in block:
        if ent.dxftype() == "LINE":
            xs += [ent.dxf.start.x, ent.dxf.end.x]
            ys += [ent.dxf.start.y, ent.dxf.end.y]
        elif ent.dxftype() == "LWPOLYLINE":
            for pt in ent.get_points():
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))

    if not xs:
        return None

    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    w = xmax - xmin
    h = ymax - ymin
    return (cx, cy, w, h)


def _extract_sleeves(doc, msp) -> list[Sleeve]:
    """
    Extract all sleeve INSERT entities from sleeve layers.

    Three block patterns are handled:

    1. Named ``スリーブ(S)-Z{uid}`` / ``スリーブ（鉄）-Z{uid}`` with a single
       CIRCLE centred at (0,0): INSERT.insert == sleeve centre, diameter from
       the circle radius × 2.

    2. Named ``INS-G{uid}`` (composite block): may contain many CIRCLEs each
       at an offset from the block origin.  The INSERT.insert is the block
       origin; the actual sleeve centre for each circle is
       INSERT.insert + circle_offset.

    3. Named ``箱（鉄）-Z{uid}`` / ``スリーブ（鉄）-Z{uid}`` with no CIRCLE but
       having LINE/LWPOLYLINE geometry (box or pipe-through-slab type):
       sleeve centre = INSERT.insert + bbox centre, diameter = minimum of
       bounding-box width and height (the cross-section short axis).
    """
    sleeve_layers = _find_layers(doc, "スリーブ")

    # Cache block geometry to avoid re-reading the same block many times
    _circle_cache: dict[str, list[tuple[float, float, float]]] = {}
    _bbox_cache: dict[str, tuple[float, float, float, float] | None] = {}

    def get_circles(bname: str) -> list[tuple[float, float, float]]:
        if bname not in _circle_cache:
            _circle_cache[bname] = _get_block_circles(doc, bname)
        return _circle_cache[bname]

    def get_bbox(bname: str) -> tuple[float, float, float, float] | None:
        if bname not in _bbox_cache:
            _bbox_cache[bname] = _get_block_bbox_size(doc, bname)
        return _bbox_cache[bname]

    sleeves: list[Sleeve] = []
    uid_counter = 0

    for ins in _entities_on_layers(msp, sleeve_layers, "INSERT"):
        block_name: str = ins.dxf.name
        layer: str = ins.dxf.layer
        discipline = _discipline_from_layer(layer)
        ins_x: float = ins.dxf.insert.x
        ins_y: float = ins.dxf.insert.y

        # Determine scale factors (default 1.0)
        scale_x = getattr(ins.dxf, "xscale", 1.0) or 1.0
        scale_y = getattr(ins.dxf, "yscale", 1.0) or 1.0

        # Rotation (degrees → radians)
        rot_deg = getattr(ins.dxf, "rotation", 0.0) or 0.0
        rot_rad = math.radians(rot_deg)
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)

        # Only process blocks whose name starts with a sleeve/box keyword.
        # INS-G* composite blocks (slab labels, etc.) are NOT sleeves.
        _is_sleeve_block = any(
            kw in block_name for kw in ("スリーブ", "箱", "電気パイプ")
        )
        if not _is_sleeve_block:
            continue

        circles = get_circles(block_name)

        if circles:
            # --- Pattern 1 & 2: CIRCLE-based sleeves ---
            for ox, oy, diameter in circles:
                # Apply scale then rotation
                lx = ox * scale_x
                ly = oy * scale_y
                wx = ins_x + lx * cos_r - ly * sin_r
                wy = ins_y + lx * sin_r + ly * cos_r

                if not _in_building_range(wx, wy):
                    continue

                uid_counter += 1
                sleeves.append(
                    Sleeve(
                        id=f"{block_name}_{uid_counter}",
                        center=(wx, wy),
                        diameter=diameter,
                        layer=layer,
                        discipline=discipline,
                    )
                )
        else:
            # --- Pattern 3: Rectangular / box sleeves (no CIRCLE) ---
            # Use the INSERT point itself as the sleeve centre (block local
            # origin is already at the centre for these blocks, but we also
            # apply the bbox centre offset just in case).
            bbox = get_bbox(block_name)
            if bbox is None:
                continue  # empty block, skip

            bcx, bcy, bw, bh = bbox
            # Diameter = minimum of width/height (the smaller cross-section)
            diameter = min(bw, bh) if min(bw, bh) > 0 else max(bw, bh)
            if diameter <= 0:
                continue

            # World position: INSERT + rotated bbox centre
            lx = bcx * scale_x
            ly = bcy * scale_y
            wx = ins_x + lx * cos_r - ly * sin_r
            wy = ins_y + lx * sin_r + ly * cos_r

            if not _in_building_range(wx, wy):
                continue

            uid_counter += 1
            sleeves.append(
                Sleeve(
                    id=f"{block_name}_{uid_counter}",
                    center=(wx, wy),
                    diameter=diameter,
                    layer=layer,
                    discipline=discipline,
                )
            )

    return sleeves


# ---------------------------------------------------------------------------
# Grid line extraction
# ---------------------------------------------------------------------------

def _extract_grid_lines(doc, msp) -> list[GridLine]:
    """
    Extract grid (通り芯) LINEs.

    Grid layers have suffixes ``C131_通心`` or ``C131_通芯``.
    A line is classified as:
    - Horizontal (H) when |dy| < |dx|  → position = average Y of endpoints
    - Vertical   (V) when |dx| < |dy|  → position = average X of endpoints

    Only lines whose midpoint falls in the building range are kept.
    Near-duplicate positions (within 50 mm) are deduplicated, keeping one
    representative per unique grid position.
    """
    grid_layers = _find_layers_any(doc, ["C131_通心", "C131_通芯"])

    _H_DEDUP = 50.0
    _V_DEDUP = 50.0
    _MIN_GRID_LENGTH = 10_000.0  # grid lines must be ≥10m to filter noise

    h_positions: list[float] = []  # unique Y values for H lines
    v_positions: list[float] = []  # unique X values for V lines

    for line in _entities_on_layers(msp, grid_layers, "LINE"):
        sx, sy = line.dxf.start.x, line.dxf.start.y
        ex, ey = line.dxf.end.x, line.dxf.end.y

        dx = abs(ex - sx)
        dy = abs(ey - sy)
        length = math.hypot(dx, dy)

        # Filter out short lines (not actual grid lines)
        if length < _MIN_GRID_LENGTH:
            continue

        mx = (sx + ex) / 2.0
        my = (sy + ey) / 2.0

        if not _in_building_range(mx, my):
            continue

        if dx > dy:
            # Horizontal: position = Y
            pos = (sy + ey) / 2.0
            if all(abs(pos - p) > _H_DEDUP for p in h_positions):
                h_positions.append(pos)
        else:
            # Vertical: position = X
            pos = (sx + ex) / 2.0
            if all(abs(pos - p) > _V_DEDUP for p in v_positions):
                v_positions.append(pos)

    grid_lines: list[GridLine] = []

    for i, pos in enumerate(sorted(h_positions)):
        grid_lines.append(GridLine(axis_label=str(i + 1), direction="H", position=pos))

    for i, pos in enumerate(sorted(v_positions)):
        grid_lines.append(GridLine(axis_label=str(i + 1), direction="V", position=pos))

    return grid_lines


# ---------------------------------------------------------------------------
# Wall line extraction
# ---------------------------------------------------------------------------

def _extract_wall_lines(doc, msp) -> list[WallLine]:
    """
    Extract wall-related LINEs and LWPOLYLINE segments.

    Wall layers:
    - ``C151_壁心``    → wall centre lines
    - ``F106_RC壁``    → RC wall outlines
    - ``A521_壁：仕上``→ wall finish lines
    - ``A422_壁：ＡＬＣ``→ ALC wall
    - ``A441_壁``      → LGS wall (suffix match)
    """
    wall_keywords = [
        "C151_壁心",
        "F106_RC壁",
        "A521_壁：仕上",
        "A422_壁：ＡＬＣ",
        "A441_壁",
    ]
    wall_layers = _find_layers_any(doc, wall_keywords)

    def _wall_type(layer_name: str) -> str:
        if "壁心" in layer_name or "C151" in layer_name:
            return "壁心"
        if "RC壁" in layer_name or "F106" in layer_name or "F105" in layer_name:
            return "RC壁"
        if "仕上" in layer_name or "A521" in layer_name:
            return "仕上"
        if "ＡＬＣ" in layer_name or "ALC" in layer_name or "A422" in layer_name:
            return "ALC"
        if "A441" in layer_name:
            return "LGS"
        return "不明"

    wall_lines: list[WallLine] = []

    for entity in msp:
        layer = entity.dxf.layer
        if layer not in set(wall_layers):
            continue

        wtype = _wall_type(layer)

        if entity.dxftype() == "LINE":
            sx, sy = entity.dxf.start.x, entity.dxf.start.y
            ex, ey = entity.dxf.end.x, entity.dxf.end.y
            if _in_building_range((sx + ex) / 2, (sy + ey) / 2):
                wall_lines.append(
                    WallLine(start=(sx, sy), end=(ex, ey), layer=layer, wall_type=wtype)
                )

        elif entity.dxftype() == "LWPOLYLINE":
            pts = list(entity.get_points())
            for i in range(len(pts) - 1):
                sx, sy = float(pts[i][0]), float(pts[i][1])
                ex, ey = float(pts[i + 1][0]), float(pts[i + 1][1])
                if _in_building_range((sx + ex) / 2, (sy + ey) / 2):
                    wall_lines.append(
                        WallLine(
                            start=(sx, sy), end=(ex, ey), layer=layer, wall_type=wtype
                        )
                    )
            # Close polyline if needed
            if entity.is_closed and len(pts) >= 2:
                sx, sy = float(pts[-1][0]), float(pts[-1][1])
                ex, ey = float(pts[0][0]), float(pts[0][1])
                if _in_building_range((sx + ex) / 2, (sy + ey) / 2):
                    wall_lines.append(
                        WallLine(
                            start=(sx, sy), end=(ex, ey), layer=layer, wall_type=wtype
                        )
                    )

    return wall_lines


# ---------------------------------------------------------------------------
# Step / recess line extraction
# ---------------------------------------------------------------------------

def _extract_step_lines(doc, msp) -> list[StepLine]:
    """
    Extract slab step (段差) and recess (床ヌスミ) lines.

    Relevant layer suffixes:
    - ``F108_3_RCスラブ段差線``
    - ``F108_5_床ヌスミ``
    """
    step_keywords = ["F108_3_RCスラブ段差線", "F108_5_床ヌスミ", "段差"]
    step_layers = _find_layers_any(doc, step_keywords)

    step_lines: list[StepLine] = []

    for entity in msp:
        layer = entity.dxf.layer
        if layer not in set(step_layers):
            continue

        if entity.dxftype() == "LINE":
            sx, sy = entity.dxf.start.x, entity.dxf.start.y
            ex, ey = entity.dxf.end.x, entity.dxf.end.y
            if _in_building_range((sx + ex) / 2, (sy + ey) / 2):
                step_lines.append(StepLine(start=(sx, sy), end=(ex, ey), layer=layer))

        elif entity.dxftype() == "LWPOLYLINE":
            pts = list(entity.get_points())
            for i in range(len(pts) - 1):
                sx, sy = float(pts[i][0]), float(pts[i][1])
                ex, ey = float(pts[i + 1][0]), float(pts[i + 1][1])
                if _in_building_range((sx + ex) / 2, (sy + ey) / 2):
                    step_lines.append(
                        StepLine(start=(sx, sy), end=(ex, ey), layer=layer)
                    )

    return step_lines


# ---------------------------------------------------------------------------
# Column line extraction
# ---------------------------------------------------------------------------

def _extract_column_lines(doc, msp) -> list[ColumnLine]:
    """
    Extract RC column outlines (F102_RC柱), S column outlines (F201_Ｓ柱),
    and wall finish lines (A521_壁：仕上) as ColumnLine objects.
    """
    col_keywords = ["F102_RC柱", "F101_RC柱", "F201_Ｓ柱", "F201_S柱"]
    col_layers = _find_layers_any(doc, col_keywords)

    col_lines: list[ColumnLine] = []

    for entity in msp:
        layer = entity.dxf.layer
        if layer not in set(col_layers):
            continue

        if entity.dxftype() == "LINE":
            sx, sy = entity.dxf.start.x, entity.dxf.start.y
            ex, ey = entity.dxf.end.x, entity.dxf.end.y
            if _in_building_range((sx + ex) / 2, (sy + ey) / 2):
                col_lines.append(ColumnLine(start=(sx, sy), end=(ex, ey), layer=layer))

        elif entity.dxftype() == "LWPOLYLINE":
            pts = list(entity.get_points())
            for i in range(len(pts) - 1):
                sx, sy = float(pts[i][0]), float(pts[i][1])
                ex, ey = float(pts[i + 1][0]), float(pts[i + 1][1])
                if _in_building_range((sx + ex) / 2, (sy + ey) / 2):
                    col_lines.append(
                        ColumnLine(start=(sx, sy), end=(ex, ey), layer=layer)
                    )
            if entity.is_closed and len(pts) >= 2:
                sx, sy = float(pts[-1][0]), float(pts[-1][1])
                ex, ey = float(pts[0][0]), float(pts[0][1])
                if _in_building_range((sx + ex) / 2, (sy + ey) / 2):
                    col_lines.append(
                        ColumnLine(start=(sx, sy), end=(ex, ey), layer=layer)
                    )

    return col_lines


# ---------------------------------------------------------------------------
# Dimension line extraction
# ---------------------------------------------------------------------------

def _extract_dim_lines(doc, msp) -> list[DimLine]:
    """
    Extract DIMENSION entities from modelspace.

    For each DIMENSION we record:
    - layer
    - measurement  (``actual_measurement`` attribute, falls back to 0.0)
    - defpoint1, defpoint2  (first two definition points)
    - text_override  (``text`` attribute if non-empty, else None)
    """
    dim_lines: list[DimLine] = []

    for entity in msp:
        if entity.dxftype() != "DIMENSION":
            continue

        try:
            layer = entity.dxf.layer

            measurement = entity.dxf.get("actual_measurement", 0.0)
            if measurement is None:
                measurement = 0.0

            try:
                dp = entity.dxf.defpoint
                defpoint1 = (dp.x, dp.y)
            except Exception:
                defpoint1 = (0.0, 0.0)

            try:
                dp2 = entity.dxf.defpoint2
                defpoint2 = (dp2.x, dp2.y)
            except Exception:
                defpoint2 = (0.0, 0.0)

            text_override: str | None = None
            try:
                txt = entity.dxf.text
                if txt and txt.strip() and txt.strip() != "<>":
                    text_override = txt.strip()
            except Exception:
                pass

            # Filter to building range using defpoint1
            if not _in_building_range(defpoint1[0], defpoint1[1]):
                # Also try defpoint2 if available
                if not _in_building_range(defpoint2[0], defpoint2[1]):
                    continue

            dim_lines.append(
                DimLine(
                    layer=layer,
                    measurement=float(measurement),
                    defpoint1=defpoint1,
                    defpoint2=defpoint2,
                    text_override=text_override,
                )
            )
        except Exception:
            # Skip malformed DIMENSION entities
            continue

    return dim_lines


# ---------------------------------------------------------------------------
# Text → Sleeve label association
# ---------------------------------------------------------------------------

def _attach_label_texts(sleeves: list[Sleeve], doc, msp) -> None:
    """
    Associate TEXT entities near each sleeve with ``label_text`` and ``fl_text``.

    Strategy:
    - Collect all TEXT/MTEXT entities on sleeve-related layers that are within
      the building range.
    - For each sleeve, find the nearest text matching a φ-pattern → label_text.
    - For each sleeve, find the nearest text matching an FL-pattern → fl_text.
      * First look on the sleeve's own layer (existing logic, radius 1500 mm).
      * If no FL found there, fall back to the nearest FL zone point from slab
        label layers (F308_スラブ / スラブラベル) — no radius limit, pure
        nearest-neighbour.  The stored value is just the FL part (e.g.
        ``"FL-225"``), not the full slab label text.
    - Search radius: _LABEL_SEARCH_RADIUS (1500 mm) for sleeve-layer texts.
    - Y-coordinate proximity is weighted double (match spec: Y-coord priority).
    """
    sleeve_layers = set(_find_layers(doc, "スリーブ"))

    # Build candidate text list from sleeve layers only (for φ and same-layer FL)
    sleeve_candidates: list[tuple[float, float, str]] = []  # (x, y, text)

    for entity in msp:
        if entity.dxftype() not in ("TEXT", "MTEXT"):
            continue

        layer = entity.dxf.layer
        if layer not in sleeve_layers:
            continue

        try:
            if entity.dxftype() == "TEXT":
                raw = entity.dxf.text or ""
            else:
                raw = entity.plain_mtext() or ""

            txt = raw.strip()
            if not txt:
                continue

            pos = entity.dxf.insert
            x, y = float(pos.x), float(pos.y)

            if not _in_building_range(x, y):
                continue

            sleeve_candidates.append((x, y, txt))
        except Exception:
            continue

    # Build FL zones from slab label layers for fallback nearest-zone lookup
    fl_zones = _build_fl_zones(doc, msp)

    for sleeve in sleeves:
        cx, cy = sleeve.center

        best_phi_dist = float("inf")
        best_phi_txt: str | None = None
        best_fl_dist = float("inf")
        best_fl_txt: str | None = None

        for tx, ty, txt in sleeve_candidates:
            # Y-priority weighted distance
            dx = tx - cx
            dy = (ty - cy) * 0.5  # halve Y so it's "double-weighted" in proximity
            dist = math.hypot(dx, dy)

            if dist > _LABEL_SEARCH_RADIUS:
                continue

            if _RE_PHI.search(txt) and dist < best_phi_dist:
                best_phi_dist = dist
                best_phi_txt = txt

            if _RE_FL.search(txt) and dist < best_fl_dist:
                best_fl_dist = dist
                best_fl_txt = txt

        if best_phi_txt is not None:
            sleeve.label_text = best_phi_txt

        if best_fl_txt is not None:
            # Found FL on the sleeve's own layer — use as-is
            sleeve.fl_text = best_fl_txt
        elif fl_zones:
            # Fallback: find the nearest slab FL zone point (no radius limit)
            best_zone_dist = float("inf")
            best_zone_fl: str | None = None
            for zx, zy, fl_val in fl_zones:
                dist = math.hypot(zx - cx, zy - cy)
                if dist < best_zone_dist:
                    best_zone_dist = dist
                    best_zone_fl = fl_val
            if best_zone_fl is not None:
                sleeve.fl_text = best_zone_fl


# ---------------------------------------------------------------------------
# FL zone helpers (slab label → positional FL lookup)
# ---------------------------------------------------------------------------

def _build_fl_zones(doc, msp) -> list[tuple[float, float, str]]:
    """
    Collect all TEXT/MTEXT entities on slab label layers (F308_スラブ,
    スラブラベル) that contain an FL pattern, and return them as a list of
    ``(x, y, fl_value)`` tuples where *fl_value* is the normalised FL string
    (e.g. ``"FL-225"``).

    These tuples form "FL zones": a sleeve with no FL text on its own layer can
    find the nearest zone point and inherit its FL value.
    """
    slab_layers = set(_find_layers_any(doc, ["F308_スラブ", "スラブラベル"]))
    fl_pattern = re.compile(r"FL\s*[+\-]\s*\d+", re.IGNORECASE)

    zones: list[tuple[float, float, str]] = []

    for entity in msp:
        if entity.dxf.layer not in slab_layers:
            continue
        if entity.dxftype() not in ("TEXT", "MTEXT"):
            continue

        try:
            if entity.dxftype() == "TEXT":
                raw = entity.dxf.text or ""
            else:
                raw = entity.plain_mtext() or ""

            pos = entity.dxf.insert
            x, y = float(pos.x), float(pos.y)

            if not _in_building_range(x, y):
                continue

            match = fl_pattern.search(raw)
            if match:
                # Normalise: remove spaces e.g. 'FL - 750' → 'FL-750'
                fl_value = re.sub(r"\s+", "", match.group(0)).upper()
                zones.append((x, y, fl_value))
        except Exception:
            continue

    return zones


# ---------------------------------------------------------------------------
# Slab level extraction
# ---------------------------------------------------------------------------

def _extract_slab_level(doc, msp) -> str | None:
    """
    Return the most common slab level text (e.g. 'FL-750') from F308_スラブ
    and related layers within the building range.  Returns None if not found.
    """
    slab_layers = set(_find_layers_any(doc, ["F308_スラブ", "スラブラベル"]))

    from collections import Counter
    level_counts: Counter = Counter()

    fl_pattern = re.compile(r"FL\s*[+\-]\s*\d+", re.IGNORECASE)

    for entity in msp:
        if entity.dxf.layer not in slab_layers:
            continue
        if entity.dxftype() not in ("TEXT", "MTEXT"):
            continue

        try:
            if entity.dxftype() == "TEXT":
                raw = entity.dxf.text or ""
            else:
                raw = entity.plain_mtext() or ""

            pos = entity.dxf.insert
            if not _in_building_range(pos.x, pos.y):
                continue

            match = fl_pattern.search(raw)
            if match:
                # Normalise: remove spaces e.g. 'FL - 750' → 'FL-750'
                normalised = re.sub(r"\s+", "", match.group(0)).upper()
                level_counts[normalised] += 1
        except Exception:
            continue

    if not level_counts:
        return None

    # Return the most frequent value (the dominant slab level for this floor)
    return level_counts.most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_dxf(filepath: str | Path) -> FloorData:
    """
    Read a DXF file and return a :class:`FloorData` containing all parsed
    geometry needed by the check logic.

    Parameters
    ----------
    filepath:
        Path to the ``.dxf`` file.

    Returns
    -------
    FloorData
        Populated dataclass.
    """
    doc = ezdxf.readfile(str(filepath))
    msp = doc.modelspace()

    sleeves = _extract_sleeves(doc, msp)
    _attach_label_texts(sleeves, doc, msp)

    grid_lines = _extract_grid_lines(doc, msp)
    wall_lines = _extract_wall_lines(doc, msp)
    step_lines = _extract_step_lines(doc, msp)
    column_lines = _extract_column_lines(doc, msp)
    dim_lines = _extract_dim_lines(doc, msp)
    slab_level = _extract_slab_level(doc, msp)

    return FloorData(
        sleeves=sleeves,
        grid_lines=grid_lines,
        wall_lines=wall_lines,
        step_lines=step_lines,
        column_lines=column_lines,
        dim_lines=dim_lines,
        slab_level=slab_level,
    )
