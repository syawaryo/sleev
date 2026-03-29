"""
checks.py - All 14 sleeve check functions for the sleeve checker project.

Each function returns a list[CheckResult].  The integration function
run_all_checks() wires them all together given FloorData objects.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .geometry import point_to_segment_distance, points_match, point_on_any_segment
from .models import (
    CheckResult,
    ColumnLine,
    DimLine,
    FloorData,
    GridLine,
    Sleeve,
    StepLine,
    WallLine,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DRAIN_CODES = ["SD", "RD", "WD", "排水", "汚水", "雨水"]

_DEFAULT_WALL_THICKNESS: dict[str, float] = {
    "RC": 0,
    "LGS": 150,
    "ALC": 150,
    "PCa": 200,
    "パネル": 100,
    "不明": 200,
}

# ---------------------------------------------------------------------------
# #2 check_discipline
# ---------------------------------------------------------------------------

def check_discipline(sleeve: Sleeve) -> list[CheckResult]:
    """Check #2: discipline label exists (label_text non-empty)."""
    if sleeve.label_text and sleeve.label_text.strip():
        return [CheckResult(
            check_id=2,
            check_name="設備種別記載",
            severity="OK",
            sleeve=sleeve,
            message="設備種別記載あり",
        )]
    return [CheckResult(
        check_id=2,
        check_name="設備種別記載",
        severity="NG",
        sleeve=sleeve,
        message="設備種別ラベルなし",
    )]


# ---------------------------------------------------------------------------
# #3 check_diameter_label
# ---------------------------------------------------------------------------

_RE_DIAMETER = re.compile(r"[φΦø]\s*\d+|\d+\s*[φΦø]")


def check_diameter_label(sleeve: Sleeve) -> list[CheckResult]:
    """Check #3: label_text contains a diameter mark (φ/Φ/ø + number)."""
    label = sleeve.label_text or ""
    if _RE_DIAMETER.search(label):
        return [CheckResult(
            check_id=3,
            check_name="口径・外径記載",
            severity="OK",
            sleeve=sleeve,
            message="口径記載あり",
        )]
    return [CheckResult(
        check_id=3,
        check_name="口径・外径記載",
        severity="NG",
        sleeve=sleeve,
        message="φ記載なし",
        related_coords=[sleeve.center],
    )]


# ---------------------------------------------------------------------------
# #5 check_gradient
# ---------------------------------------------------------------------------

_RE_GRADIENT = re.compile(r"FL|1/\d+", re.IGNORECASE)


def check_gradient(sleeve: Sleeve) -> list[CheckResult]:
    """Check #5: drain sleeves must have FL or gradient annotation."""
    label = sleeve.label_text or ""
    is_drain = any(code in label for code in DRAIN_CODES)

    if not is_drain:
        return [CheckResult(
            check_id=5,
            check_name="勾配記載",
            severity="OK",
            sleeve=sleeve,
            message="排水スリーブではないためスキップ",
        )]

    fl = sleeve.fl_text or ""
    if _RE_GRADIENT.search(fl) or _RE_GRADIENT.search(label):
        return [CheckResult(
            check_id=5,
            check_name="勾配記載",
            severity="OK",
            sleeve=sleeve,
            message="勾配または高さ記載あり",
        )]

    return [CheckResult(
        check_id=5,
        check_name="勾配記載",
        severity="WARNING",
        sleeve=sleeve,
        message="排水スリーブだが勾配・FL記載なし",
        related_coords=[sleeve.center],
    )]


# ---------------------------------------------------------------------------
# #8 check_fl_label
# ---------------------------------------------------------------------------

_RE_FL = re.compile(r"FL\s*[±+\-]\s*\d+", re.IGNORECASE)


def check_fl_label(sleeve: Sleeve) -> list[CheckResult]:
    """Check #8: fl_text matches FL±/+/- number pattern."""
    fl = sleeve.fl_text or ""
    if _RE_FL.search(fl):
        return [CheckResult(
            check_id=8,
            check_name="FL記載",
            severity="OK",
            sleeve=sleeve,
            message="FL記載あり",
        )]
    return [CheckResult(
        check_id=8,
        check_name="FL記載",
        severity="NG",
        sleeve=sleeve,
        message="FL記載なし・形式不正",
        related_coords=[sleeve.center],
    )]


# ---------------------------------------------------------------------------
# #14 check_sleeve_number
# ---------------------------------------------------------------------------

_RE_PN = re.compile(r"P-N-\d+")


def check_sleeve_number(sleeve: Sleeve) -> list[CheckResult]:
    """Check #14: pn_number matches P-N-{digits}."""
    pn = sleeve.pn_number or ""
    if _RE_PN.fullmatch(pn.strip()):
        return [CheckResult(
            check_id=14,
            check_name="スリーブ番号記載",
            severity="OK",
            sleeve=sleeve,
            message="番号記載あり",
        )]
    return [CheckResult(
        check_id=14,
        check_name="スリーブ番号記載",
        severity="NG",
        sleeve=sleeve,
        message="P-N-番号記載なし・形式不正",
        related_coords=[sleeve.center],
    )]


# ---------------------------------------------------------------------------
# #6 check_lower_wall
# ---------------------------------------------------------------------------

def check_lower_wall(
    sleeve: Sleeve,
    lower_walls: list[WallLine],
    wall_thickness: dict[str, float] | None = None,
) -> list[CheckResult]:
    """
    Check #6: sleeve must not overlap the wall below it.

    For RC walls: threshold = sleeve.diameter / 2
    For other walls: threshold = sleeve.diameter / 2 + wall_thickness[wall_type] / 2
    """
    if wall_thickness is None:
        wall_thickness = _DEFAULT_WALL_THICKNESS

    results: list[CheckResult] = []

    for wall in lower_walls:
        wtype = wall.wall_type

        # Determine threshold
        if wtype in ("RC壁", "RC"):
            # RC exterior surface lines — sleeve edge to surface
            threshold = sleeve.diameter / 2.0
        else:
            # Normalize wall type key for lookup
            tk = wtype
            if tk not in wall_thickness:
                # Try stripping Japanese decorators
                for key in wall_thickness:
                    if key in wtype:
                        tk = key
                        break
                else:
                    tk = "不明"
            thickness = wall_thickness.get(tk, wall_thickness.get("不明", 200))
            threshold = sleeve.diameter / 2.0 + thickness / 2.0

        dist = point_to_segment_distance(sleeve.center, wall.start, wall.end)
        if dist < threshold:
            results.append(CheckResult(
                check_id=6,
                check_name="下階壁干渉",
                severity="NG",
                sleeve=sleeve,
                message=f"下階壁（{wtype}）との距離 {dist:.1f}mm < しきい値 {threshold:.1f}mm",
                related_coords=[sleeve.center, wall.start, wall.end],
            ))

    if not results:
        results.append(CheckResult(
            check_id=6,
            check_name="下階壁干渉",
            severity="OK",
            sleeve=sleeve,
            message="下階壁との干渉なし",
        ))

    return results


# ---------------------------------------------------------------------------
# #7 check_step_slab
# ---------------------------------------------------------------------------

def check_step_slab(
    sleeve: Sleeve,
    step_lines: list[StepLine],
    threshold: float | None,
) -> list[CheckResult]:
    """Check #7: sleeve proximity to slab step lines."""
    if threshold is None:
        return [CheckResult(
            check_id=7,
            check_name="段差近接",
            severity="OK",
            sleeve=sleeve,
            message="しきい値未設定（スキップ）",
        )]

    results: list[CheckResult] = []

    for step in step_lines:
        dist = point_to_segment_distance(sleeve.center, step.start, step.end)
        if dist < threshold:
            results.append(CheckResult(
                check_id=7,
                check_name="段差近接",
                severity="WARNING",
                sleeve=sleeve,
                message=f"段差線との距離 {dist:.1f}mm < しきい値 {threshold:.1f}mm",
                related_coords=[sleeve.center, step.start, step.end],
            ))

    if not results:
        results.append(CheckResult(
            check_id=7,
            check_name="段差近接",
            severity="OK",
            sleeve=sleeve,
            message="段差線との近接なし",
        ))

    return results


# ---------------------------------------------------------------------------
# #10 check_step_dim
# ---------------------------------------------------------------------------

def check_step_dim(
    dim: DimLine,
    step_lines: list[StepLine],
    tolerance: float = 5.0,
) -> list[CheckResult]:
    """Check #10: dimension defpoint1 must not lie on a step line."""
    segments = [(s.start, s.end) for s in step_lines]
    if point_on_any_segment(dim.defpoint1, segments, tolerance):
        return [CheckResult(
            check_id=10,
            check_name="段差基準寸法",
            severity="NG",
            sleeve=None,
            message=f"寸法基点が段差線上にあります: {dim.defpoint1}",
            related_coords=[dim.defpoint1, dim.defpoint2],
        )]
    return [CheckResult(
        check_id=10,
        check_name="段差基準寸法",
        severity="OK",
        sleeve=None,
        message="段差線上の寸法基点なし",
    )]


# ---------------------------------------------------------------------------
# #11 check_sleeve_center_dim
# ---------------------------------------------------------------------------

def check_sleeve_center_dim(
    dim: DimLine,
    sleeves: list[Sleeve],
    tolerance: float = 5.0,
) -> list[CheckResult]:
    """Check #11: dimension must not span directly between two sleeve centres."""
    dp1_sleeve = next(
        (s for s in sleeves if points_match(dim.defpoint1, s.center, tolerance)),
        None,
    )
    if dp1_sleeve is None:
        return [CheckResult(
            check_id=11,
            check_name="スリーブ芯寸法",
            severity="OK",
            sleeve=None,
            message="スリーブ間寸法なし",
        )]

    dp2_sleeve = next(
        (
            s for s in sleeves
            if s is not dp1_sleeve and points_match(dim.defpoint2, s.center, tolerance)
        ),
        None,
    )
    if dp2_sleeve is not None:
        return [CheckResult(
            check_id=11,
            check_name="スリーブ芯寸法",
            severity="NG",
            sleeve=dp1_sleeve,
            message=(
                f"スリーブ芯間の寸法が記載されています: "
                f"{dp1_sleeve.id} ↔ {dp2_sleeve.id}"
            ),
            related_coords=[dim.defpoint1, dim.defpoint2],
        )]

    return [CheckResult(
        check_id=11,
        check_name="スリーブ芯寸法",
        severity="OK",
        sleeve=None,
        message="スリーブ間寸法なし",
    )]


# ---------------------------------------------------------------------------
# #12 check_column_wall_dim
# ---------------------------------------------------------------------------

def check_column_wall_dim(
    dim: DimLine,
    column_lines: list[ColumnLine],
    tolerance: float = 5.0,
) -> list[CheckResult]:
    """Check #12: dimension defpoint1 must not lie on a column/wall-finish line."""
    segments = [(c.start, c.end) for c in column_lines]
    if point_on_any_segment(dim.defpoint1, segments, tolerance):
        return [CheckResult(
            check_id=12,
            check_name="柱・壁仕上寸法",
            severity="NG",
            sleeve=None,
            message=f"寸法基点が柱・壁仕上線上にあります: {dim.defpoint1}",
            related_coords=[dim.defpoint1, dim.defpoint2],
        )]
    return [CheckResult(
        check_id=12,
        check_name="柱・壁仕上寸法",
        severity="OK",
        sleeve=None,
        message="柱・壁仕上線上の寸法基点なし",
    )]


# ---------------------------------------------------------------------------
# #4 check_dim_sum
# ---------------------------------------------------------------------------

def check_dim_sum(
    dims: list[DimLine],
    grids: list[GridLine],
) -> list[CheckResult]:
    """
    Check #4: Detect continuous dimension chains and verify their sum
    equals the grid-to-grid span.

    Algorithm:
    1. Classify dims as horizontal or vertical by comparing defpoint2/3 spread.
    2. Group by dimension line position (defpoint1 Y for horiz, X for vert).
    3. Within each group, find continuous chains (endpoint gap < 50mm).
    4. If chain endpoints are near grid lines (< 200mm), compare
       chain sum vs grid span.
    """
    results: list[CheckResult] = []

    v_grids = sorted([g for g in grids if g.direction == "V"], key=lambda g: g.position)
    h_grids = sorted([g for g in grids if g.direction == "H"], key=lambda g: g.position)

    CHAIN_GAP = 50.0      # max gap between adjacent dims in a chain
    GRID_SNAP = 200.0     # max distance from chain end to grid line
    SUM_TOLERANCE = 5.0   # mm
    GROUP_BIN = 50.0      # bin size for grouping dim line positions

    def _find_nearest_grid(
        pos: float, grid_list: list[GridLine]
    ) -> tuple[GridLine | None, float]:
        if not grid_list:
            return None, float("inf")
        best = min(grid_list, key=lambda g: abs(g.position - pos))
        return best, abs(best.position - pos)

    def _detect_chains(
        dim_group: list[DimLine],
        get_start: callable,
        get_end: callable,
        grid_list: list[GridLine],
        axis: str,
    ) -> None:
        if len(dim_group) < 2:
            return

        dim_group.sort(key=lambda d: get_start(d))

        # Build continuous chains
        chains: list[list[DimLine]] = []
        chain: list[DimLine] = [dim_group[0]]

        for i in range(1, len(dim_group)):
            prev_end = get_end(chain[-1])
            curr_start = get_start(dim_group[i])
            if abs(curr_start - prev_end) < CHAIN_GAP:
                chain.append(dim_group[i])
            else:
                if len(chain) >= 2:
                    chains.append(chain)
                chain = [dim_group[i]]

        if len(chain) >= 2:
            chains.append(chain)

        # Check each chain against grid span
        for ch in chains:
            chain_start = get_start(ch[0])
            chain_end = get_end(ch[-1])
            chain_sum = sum(d.measurement for d in ch)

            g_start, d_start = _find_nearest_grid(chain_start, grid_list)
            g_end, d_end = _find_nearest_grid(chain_end, grid_list)

            if (g_start is None or g_end is None
                    or g_start.axis_label == g_end.axis_label):
                continue

            grid_span = abs(g_end.position - g_start.position)

            # Only check chains that reasonably span between grids
            if d_start > GRID_SNAP or d_end > GRID_SNAP:
                continue

            if axis == "X":
                # Horizontal chain: coords are (x_start, y_dimline), (x_end, y_dimline)
                coords = [(chain_start, ch[0].defpoint1[1]),
                           (chain_end, ch[-1].defpoint1[1])]
            else:
                # Vertical chain: coords are (x_dimline, y_start), (x_dimline, y_end)
                coords = [(ch[0].defpoint1[0], chain_start),
                           (ch[-1].defpoint1[0], chain_end)]

            # Build breakdown: each dim value listed, then sum vs grid
            dim_vals = " + ".join(f"{d.measurement:.0f}" for d in ch)

            if abs(chain_sum - grid_span) <= SUM_TOLERANCE:
                results.append(CheckResult(
                    check_id=4,
                    check_name="寸法合計",
                    severity="OK",
                    sleeve=None,
                    message=(
                        f"通り芯 {g_start.axis_label}–{g_end.axis_label} ({axis}) | "
                        f"寸法: {dim_vals} | "
                        f"合計: {chain_sum:.0f} | "
                        f"通り芯間: {grid_span:.0f}"
                    ),
                    related_coords=coords,
                ))
            else:
                diff = chain_sum - grid_span
                results.append(CheckResult(
                    check_id=4,
                    check_name="寸法合計",
                    severity="NG",
                    sleeve=None,
                    message=(
                        f"通り芯 {g_start.axis_label}–{g_end.axis_label} ({axis}) | "
                        f"寸法: {dim_vals} | "
                        f"合計: {chain_sum:.0f} | "
                        f"通り芯間: {grid_span:.0f} | "
                        f"差: {diff:+.0f}mm"
                    ),
                    related_coords=coords,
                ))

    def _is_horizontal(d: DimLine) -> bool | None:
        """Determine if dim is horizontal, vertical, or unknown."""
        if d.angle is not None:
            norm = d.angle % 360
            if norm < 45 or norm > 315 or (135 < norm < 225):
                return True
            return False
        dx = abs(d.defpoint2[0] - d.defpoint3[0])
        dy = abs(d.defpoint2[1] - d.defpoint3[1])
        if dx == 0 and dy == 0:
            return None
        return dx > dy

    # --- Horizontal dims (measure X span, grouped by dim-line Y position) ---
    h_dims: dict[float, list[DimLine]] = defaultdict(list)
    for d in dims:
        if d.measurement <= 10:
            continue
        if _is_horizontal(d) is True:
            y_bin = round(d.defpoint1[1] / GROUP_BIN) * GROUP_BIN
            h_dims[y_bin].append(d)

    for y_bin, group in h_dims.items():
        _detect_chains(
            group,
            get_start=lambda d: min(d.defpoint2[0], d.defpoint3[0]),
            get_end=lambda d: max(d.defpoint2[0], d.defpoint3[0]),
            grid_list=v_grids,
            axis="X",
        )

    # --- Vertical dims (measure Y span, grouped by dim-line X position) ---
    v_dims: dict[float, list[DimLine]] = defaultdict(list)
    for d in dims:
        if d.measurement <= 10:
            continue
        if _is_horizontal(d) is False:
            x_bin = round(d.defpoint1[0] / GROUP_BIN) * GROUP_BIN
            v_dims[x_bin].append(d)

    for x_bin, group in v_dims.items():
        _detect_chains(
            group,
            get_start=lambda d: min(d.defpoint2[1], d.defpoint3[1]),
            get_end=lambda d: max(d.defpoint2[1], d.defpoint3[1]),
            grid_list=h_grids,
            axis="Y",
        )

    if not results:
        results.append(CheckResult(
            check_id=4,
            check_name="寸法合計",
            severity="OK",
            sleeve=None,
            message="連続寸法チェーンなし",
        ))

    return results


# ---------------------------------------------------------------------------
# #9 check_both_sides
# ---------------------------------------------------------------------------

_SEARCH_RADIUS = 1500.0


def check_both_sides(
    sleeve: Sleeve,
    dims: list[DimLine],
    grids: list[GridLine],
    tolerance: float = 100.0,
) -> list[CheckResult]:
    """
    Check #9: For each sleeve, there must be dimension lines referencing grid
    lines on BOTH sides (left+right for X axis, top+bottom for Y axis).

    Strategy:
    1. Collect dims within _SEARCH_RADIUS of the sleeve centre.
    2. For each dim, check if its defpoints match any grid position.
    3. Classify matched grids as left/right (V grids) or top/bottom (H grids).
    4. If only one side covered in either axis → NG.
    """
    cx, cy = sleeve.center

    # Nearby dims
    nearby = [
        d for d in dims
        if (
            abs(d.defpoint1[0] - cx) <= _SEARCH_RADIUS
            and abs(d.defpoint1[1] - cy) <= _SEARCH_RADIUS
        ) or (
            abs(d.defpoint2[0] - cx) <= _SEARCH_RADIUS
            and abs(d.defpoint2[1] - cy) <= _SEARCH_RADIUS
        )
    ]

    if not nearby:
        # No dims near this sleeve → cannot verify
        return [CheckResult(
            check_id=9,
            check_name="両側寸法",
            severity="OK",
            sleeve=sleeve,
            message="近傍寸法なし（スキップ）",
        )]

    v_grids = [g for g in grids if g.direction == "V"]
    h_grids = [g for g in grids if g.direction == "H"]

    # Collect grid positions referenced by nearby dims
    left_refs: list[float] = []   # V grid X < cx
    right_refs: list[float] = []  # V grid X > cx
    bottom_refs: list[float] = []  # H grid Y < cy
    top_refs: list[float] = []    # H grid Y > cy

    for dim in nearby:
        for pt in (dim.defpoint1, dim.defpoint2):
            # Match against V grids
            for g in v_grids:
                if abs(pt[0] - g.position) <= tolerance:
                    if g.position < cx:
                        left_refs.append(g.position)
                    elif g.position > cx:
                        right_refs.append(g.position)
            # Match against H grids
            for g in h_grids:
                if abs(pt[1] - g.position) <= tolerance:
                    if g.position < cy:
                        bottom_refs.append(g.position)
                    elif g.position > cy:
                        top_refs.append(g.position)

    results: list[CheckResult] = []

    # Check X axis (need both left and right)
    if v_grids:
        if left_refs and right_refs:
            results.append(CheckResult(
                check_id=9,
                check_name="両側寸法",
                severity="OK",
                sleeve=sleeve,
                message="X軸両側の通芯寸法あり",
            ))
        elif left_refs or right_refs:
            side = "左" if left_refs else "右"
            results.append(CheckResult(
                check_id=9,
                check_name="両側寸法",
                severity="NG",
                sleeve=sleeve,
                message=f"X軸片側（{side}側）のみ通芯寸法あり",
                related_coords=[sleeve.center],
            ))

    # Check Y axis (need both top and bottom)
    if h_grids:
        if bottom_refs and top_refs:
            results.append(CheckResult(
                check_id=9,
                check_name="両側寸法",
                severity="OK",
                sleeve=sleeve,
                message="Y軸両側の通芯寸法あり",
            ))
        elif bottom_refs or top_refs:
            side = "下" if bottom_refs else "上"
            results.append(CheckResult(
                check_id=9,
                check_name="両側寸法",
                severity="NG",
                sleeve=sleeve,
                message=f"Y軸片側（{side}側）のみ通芯寸法あり",
                related_coords=[sleeve.center],
            ))

    if not results:
        results.append(CheckResult(
            check_id=9,
            check_name="両側寸法",
            severity="OK",
            sleeve=sleeve,
            message="通芯グリッドなし（スキップ）",
        ))

    return results


# ---------------------------------------------------------------------------
# #13 check_dim_notation
# ---------------------------------------------------------------------------

_RE_MM_SUFFIX = re.compile(r"\d+mm", re.IGNORECASE)
_RE_COMMA_SEP = re.compile(r"\d+,\d+")
_RE_DECIMAL = re.compile(r"\d+\.\d+")


def check_dim_notation(dims: list[DimLine]) -> list[CheckResult]:
    """
    Check #13: All dimension text overrides should follow a consistent notation.

    Patterns detected:
    - mm_suffix: "150mm"
    - comma_sep: "1,500"
    - decimal:   "1.5"
    - plain:     plain integer, no special format

    If multiple patterns are present → WARNING.
    """
    overrides = [d.text_override for d in dims if d.text_override is not None]

    if not overrides:
        return [CheckResult(
            check_id=13,
            check_name="寸法表記統一",
            severity="OK",
            sleeve=None,
            message="テキストオーバーライドなし",
        )]

    patterns_found: set[str] = set()

    for txt in overrides:
        if _RE_MM_SUFFIX.search(txt):
            patterns_found.add("mm_suffix")
        elif _RE_COMMA_SEP.search(txt):
            patterns_found.add("comma_sep")
        elif _RE_DECIMAL.search(txt):
            patterns_found.add("decimal")
        else:
            patterns_found.add("plain")

    if len(patterns_found) > 1:
        return [CheckResult(
            check_id=13,
            check_name="寸法表記統一",
            severity="WARNING",
            sleeve=None,
            message=f"寸法表記が混在しています: {sorted(patterns_found)}",
        )]

    return [CheckResult(
        check_id=13,
        check_name="寸法表記統一",
        severity="OK",
        sleeve=None,
        message=f"寸法表記統一: {sorted(patterns_found)}",
    )]


# ---------------------------------------------------------------------------
# Integration: run_all_checks
# ---------------------------------------------------------------------------

def run_all_checks(
    floor_2f: FloorData,
    floor_1f: FloorData | None = None,
    wall_thickness: dict[str, float] | None = None,
    step_threshold: float | None = None,
) -> list[CheckResult]:
    """
    Run all checks against the provided floor data.

    Parameters
    ----------
    floor_2f:
        Primary floor (2F sleeve drawing) — the floor being checked.
    floor_1f:
        Lower floor (1F) providing wall data for check #6.
    wall_thickness:
        Dict mapping wall type → thickness in mm.  Defaults to
        ``_DEFAULT_WALL_THICKNESS``.
    step_threshold:
        Minimum allowed distance (mm) between a sleeve and a step line
        for check #7.  Pass None to skip.

    Returns
    -------
    list[CheckResult]
    """
    if wall_thickness is None:
        wall_thickness = dict(_DEFAULT_WALL_THICKNESS)

    results: list[CheckResult] = []

    lower_walls = floor_1f.wall_lines if floor_1f is not None else []

    # --- Per-sleeve text/geometry checks ---
    for sleeve in floor_2f.sleeves:
        results.extend(check_discipline(sleeve))          # #2
        results.extend(check_diameter_label(sleeve))       # #3
        results.extend(check_gradient(sleeve))             # #5
        results.extend(check_fl_label(sleeve))             # #8
        results.extend(check_sleeve_number(sleeve))        # #14
        results.extend(check_step_slab(sleeve, floor_2f.step_lines, step_threshold))  # #7

        if lower_walls:
            results.extend(check_lower_wall(sleeve, lower_walls, wall_thickness))  # #6

    # --- Global dim checks ---
    results.extend(check_dim_sum(floor_2f.dim_lines, floor_2f.grid_lines))   # #4
    results.extend(check_dim_notation(floor_2f.dim_lines))                    # #13

    # --- Per-dim checks ---
    for dim in floor_2f.dim_lines:
        results.extend(check_step_dim(dim, floor_2f.step_lines))               # #10
        results.extend(check_sleeve_center_dim(dim, floor_2f.sleeves))         # #11
        results.extend(check_column_wall_dim(dim, floor_2f.column_lines))      # #12

    # --- Per-sleeve both-sides check ---
    for sleeve in floor_2f.sleeves:
        results.extend(check_both_sides(sleeve, floor_2f.dim_lines, floor_2f.grid_lines))  # #9

    return results
