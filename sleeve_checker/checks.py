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
    sleeve: Sleeve,
    dims: list[DimLine],
    step_lines: list[StepLine],
    sleeve_tolerance: float = 50.0,
    step_tolerance: float = 5.0,
) -> list[CheckResult]:
    """Check #10: sleeve-related dims must not originate from a step line.

    For each dimension whose defpoint2 or defpoint3 is near the sleeve
    centre, check whether that sleeve-side defpoint sits on a step line.
    If so, the dimension is measuring from a step (formwork edge) rather
    than from a reliable reference — flag as NG.
    """
    if not step_lines:
        return [CheckResult(
            check_id=10,
            check_name="段差基準寸法",
            severity="OK",
            sleeve=sleeve,
            message="段差線なし（スキップ）",
        )]

    step_segs = [(s.start, s.end) for s in step_lines]
    results: list[CheckResult] = []

    for dim in dims:
        # Find which defpoint(s) match the sleeve centre
        dp2_match = points_match(dim.defpoint2, sleeve.center, sleeve_tolerance)
        dp3_match = points_match(dim.defpoint3, sleeve.center, sleeve_tolerance)

        if not dp2_match and not dp3_match:
            continue

        # Check the sleeve-side defpoint(s) against step lines
        sleeve_pts = []
        if dp2_match:
            sleeve_pts.append(dim.defpoint2)
        if dp3_match:
            sleeve_pts.append(dim.defpoint3)

        for pt in sleeve_pts:
            if point_on_any_segment(pt, step_segs, step_tolerance):
                results.append(CheckResult(
                    check_id=10,
                    check_name="段差基準寸法",
                    severity="NG",
                    sleeve=sleeve,
                    message=f"スリーブ寸法の基点が段差線上: {pt}",
                    related_coords=[pt, sleeve.center],
                ))

    if not results:
        results.append(CheckResult(
            check_id=10,
            check_name="段差基準寸法",
            severity="OK",
            sleeve=sleeve,
            message="段差線上の寸法基点なし",
        ))

    return results


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
            related_coords=[dim.defpoint1],
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
# #9 check_position_determinacy
# ---------------------------------------------------------------------------


def check_position_determinacy(
    sleeves: list[Sleeve],
    dims: list[DimLine],
    grids: list[GridLine],
    sleeve_margin: float = 30.0,
    grid_tolerance: float = 100.0,
) -> list[CheckResult]:
    """Check #9: each sleeve's position must be determinable from dimensions.

    For each axis (X via V-grids, Y via H-grids), a sleeve is "resolved" if:
      - a dimension directly links it to a grid line, OR
      - a dimension links it to another sleeve that is already resolved.

    Algorithm (per axis):
    1. Build edges: dim connects sleeve↔grid or sleeve↔sleeve.
    2. Mark sleeves with a direct grid dim as resolved.
    3. Propagate through sleeve↔sleeve dims (BFS).
    4. Unresolved sleeves → NG.

    The sleeve match tolerance is ``sleeve.diameter / 2 + sleeve_margin``
    because dimension extension lines often originate from the sleeve edge
    rather than the centre.
    """
    if not sleeves:
        return []

    v_grid_positions = [g.position for g in grids if g.direction == "V"]
    h_grid_positions = [g.position for g in grids if g.direction == "H"]

    def _near_any_grid(val: float, grid_positions: list[float]) -> bool:
        return any(abs(val - gp) <= grid_tolerance for gp in grid_positions)

    def _match_sleeves(pt: tuple[float, float], axis: str) -> list[Sleeve]:
        """Return *all* sleeves whose coordinate on *axis* matches *pt*.

        For a vertical dim (axis="Y"), any sleeve whose Y is within
        ``diameter/2 + margin`` of ``pt[1]`` is a match — regardless of X.
        This correctly handles drawings where the dim extension-line origin
        is horizontally offset from the sleeve centre.
        """
        idx = 0 if axis == "X" else 1
        matched: list[Sleeve] = []
        for s in sleeves:
            tol = s.diameter / 2.0 + sleeve_margin
            if abs(pt[idx] - s.center[idx]) <= tol:
                matched.append(s)
        return matched

    def _is_horizontal(d: DimLine) -> bool | None:
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

    def _resolve_axis(
        axis: str,
        grid_positions: list[float],
    ) -> dict[str, bool]:
        """Return {sleeve.id: resolved} for one axis.

        Resolution propagates through:
        1. Same-axis dims (horizontal dims for X, vertical dims for Y):
           sleeve↔grid → resolved; sleeve↔sleeve → BFS edge.
        2. Cross-axis dims (vertical dims for X, horizontal dims for Y):
           sleeve↔sleeve edges only.  A vertical dim chain proves the
           connected sleeves share the same X coordinate, so if one has
           X resolved the others do too (and vice-versa for Y).
        """
        resolved: dict[str, bool] = {s.id: False for s in sleeves}
        sleeve_edges: dict[str, list[str]] = {s.id: [] for s in sleeves}

        is_x = axis == "X"
        cross_axis = "Y" if is_x else "X"

        for d in dims:
            h = _is_horizontal(d)
            dp2, dp3 = d.defpoint2, d.defpoint3

            same_axis = (is_x and h is True) or (not is_x and h is False)
            cross = (is_x and h is False) or (not is_x and h is True)

            if same_axis:
                # Same-axis: sleeve↔grid resolves, sleeve↔sleeve builds edge
                ss2 = _match_sleeves(dp2, axis)
                ss3 = _match_sleeves(dp3, axis)

                g2 = _near_any_grid(dp2[0] if is_x else dp2[1], grid_positions)
                g3 = _near_any_grid(dp3[0] if is_x else dp3[1], grid_positions)

                if g3:
                    for s in ss2:
                        resolved[s.id] = True
                if g2:
                    for s in ss3:
                        resolved[s.id] = True

                # sleeve ↔ sleeve edges between all pairs
                for s2 in ss2:
                    for s3 in ss3:
                        if s2.id != s3.id:
                            sleeve_edges[s2.id].append(s3.id)
                            sleeve_edges[s3.id].append(s2.id)

            elif cross:
                # Cross-axis: a horizontal dim connects sleeves that share Y;
                # a vertical dim connects sleeves that share X.
                # Match using the dim's own measurement axis (horizontal→X,
                # vertical→Y) so that the perpendicular offset doesn't break
                # the match.
                dim_axis = "X" if h else "Y"
                ss2 = _match_sleeves(dp2, dim_axis)
                ss3 = _match_sleeves(dp3, dim_axis)

                for s2 in ss2:
                    for s3 in ss3:
                        if s2.id != s3.id:
                            sleeve_edges[s2.id].append(s3.id)
                            sleeve_edges[s3.id].append(s2.id)

        # BFS propagation
        queue = [sid for sid, r in resolved.items() if r]
        visited = set(queue)
        while queue:
            current = queue.pop(0)
            for neighbor in sleeve_edges[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    resolved[neighbor] = True
                    queue.append(neighbor)

        return resolved

    results: list[CheckResult] = []
    sleeve_map = {s.id: s for s in sleeves}

    x_resolved = _resolve_axis("X", v_grid_positions) if v_grid_positions else None
    y_resolved = _resolve_axis("Y", h_grid_positions) if h_grid_positions else None

    for s in sleeves:
        x_ok = x_resolved[s.id] if x_resolved is not None else True
        y_ok = y_resolved[s.id] if y_resolved is not None else True

        if x_ok and y_ok:
            results.append(CheckResult(
                check_id=9,
                check_name="位置特定寸法",
                severity="OK",
                sleeve=s,
                message="X・Y方向とも位置特定可能",
            ))
        else:
            missing = []
            if not x_ok:
                missing.append("X")
            if not y_ok:
                missing.append("Y")
            results.append(CheckResult(
                check_id=9,
                check_name="位置特定寸法",
                severity="NG",
                sleeve=s,
                message=f"{'・'.join(missing)}方向の位置が寸法から特定できません",
                related_coords=[s.center],
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

    # --- Per-sleeve dim checks ---
    for sleeve in floor_2f.sleeves:
        results.extend(check_step_dim(sleeve, floor_2f.dim_lines, floor_2f.step_lines))  # #10

    # --- Per-dim checks ---
    for dim in floor_2f.dim_lines:
        results.extend(check_sleeve_center_dim(dim, floor_2f.sleeves))         # #11
        results.extend(check_column_wall_dim(dim, floor_2f.column_lines))      # #12

    # --- Position determinacy (graph-based) ---
    results.extend(check_position_determinacy(
        floor_2f.sleeves, floor_2f.dim_lines, floor_2f.grid_lines,
    ))  # #9

    return results
