"""
checks.py - All 14 sleeve check functions for the sleeve checker project.

Each function returns a list[CheckResult].  The integration function
run_all_checks() wires them all together given FloorData objects.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

from .geometry import point_to_segment_distance, points_match, point_on_any_segment
from .models import (
    CheckResult,
    ColumnLine,
    DimLine,
    FloorData,
    GridLine,
    SlabLabel,
    Sleeve,
    StepLine,
    WallLine,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DRAIN_CODES = ["SD", "RD", "WD", "KD", "CDW", "SPD", "D:", "排水", "汚水", "雨水"]

_DEFAULT_WALL_THICKNESS: dict[str, float] = {
    "RC": 0,
    "LGS": 150,
    "ALC": 150,
    "PCa": 200,
    "パネル": 100,
    "CB": 150,
    "耐火被覆": 50,
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

_RE_OUTER = re.compile(r"外径\s*\d+\s*[φΦø]?")
# Match φ+number, number+φ, or number+A (pipe size like 150A)
_RE_PHI_NUM = re.compile(r"(\d+)\s*[φΦø]|[φΦø]\s*(\d+)|(\d+)A\b")


def check_diameter_label(sleeve: Sleeve) -> list[CheckResult]:
    """Check #3: diameter_text contains both nominal diameter (呼び口径) and outer diameter (外径)."""
    txt = sleeve.diameter_text or ""
    # Also check label_text — full-form texts like "KD 175φ(外径180φ)100A"
    # may land in label_text when the equipment code matched
    label = sleeve.label_text or ""
    combined = f"{txt} {label}"

    has_outer = bool(_RE_OUTER.search(combined))
    # To detect nominal diameter, strip out 外径 portions first so "外径230φ" doesn't false-match
    stripped = _RE_OUTER.sub("", combined)
    has_nominal = bool(_RE_PHI_NUM.search(stripped))

    if has_nominal and has_outer:
        return [CheckResult(
            check_id=3,
            check_name="口径・外径記載",
            severity="OK",
            sleeve=sleeve,
            message="呼び口径・外径記載あり",
        )]

    missing = []
    if not has_nominal:
        missing.append("呼び口径")
    if not has_outer:
        missing.append("外径")

    return [CheckResult(
        check_id=3,
        check_name="口径・外径記載",
        severity="NG",
        sleeve=sleeve,
        message=f"{'・'.join(missing)}の記載なし",
        related_coords=[sleeve.center],
    )]


# ---------------------------------------------------------------------------
# #5 check_gradient
# ---------------------------------------------------------------------------

_RE_GRADIENT = re.compile(r"FL|1/\d+", re.IGNORECASE)

_GRADIENT_SEARCH_RADIUS = 1500.0  # mm — search radius for nearby gradient info


def check_gradient(
    sleeve: Sleeve,
    pn_labels: list | None = None,
    slab_zones: list | None = None,
    slab_labels: list | None = None,
    water_gradients: list | None = None,
) -> list[CheckResult]:
    """Check #5: drain sleeves — collect gradient/flow info and flag for review.

    For drain sleeves, report:
    - FL value on sleeve itself
    - P-N number (pipe route)
    - Nearby water gradient text (水勾配)
    - Nearby slab gradient (range slab label like 350～300)
    """
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

    pn_labels = pn_labels or []
    slab_zones = slab_zones or []
    slab_labels = slab_labels or []
    water_gradients = water_gradients or []
    sx, sy = sleeve.center
    r = _GRADIENT_SEARCH_RADIUS

    # --- FL value on sleeve itself ---
    fl = sleeve.fl_text or ""
    has_fl = bool(_RE_GRADIENT.search(fl) or _RE_GRADIENT.search(label))

    # --- P-N number (use pre-assigned first, fallback to nearest) ---
    pn_str = sleeve.pn_number or ""
    if not pn_str:
        for pn in pn_labels:
            dist = math.hypot(sx - pn.x, sy - pn.y)
            if dist < r:
                pn_str = pn.text
                break

    # --- Nearby water gradient text (水勾配) ---
    nearest_wg_dist = float("inf")
    nearest_wg_direction = ""
    for wg in water_gradients:
        dist = math.hypot(sx - wg.x, sy - wg.y)
        if dist < nearest_wg_dist:
            nearest_wg_dist = dist
            nearest_wg_direction = wg.direction
    has_water_gradient = nearest_wg_dist <= r

    # --- Nearby slab gradient (range label like 350～300) ---
    nearest_slab_gradient: str | None = None
    nearest_sg_dist = float("inf")
    for sl in slab_labels:
        if "～" not in sl.level and "~" not in sl.level:
            continue
        dist = math.hypot(sx - sl.x, sy - sl.y)
        if dist < r and dist < nearest_sg_dist:
            nearest_slab_gradient = sl.level
            nearest_sg_dist = dist

    # --- Build detail message ---
    details: list[str] = []
    details.append(f"FL記載: {'あり (' + fl + ')' if has_fl else 'なし'}")
    if pn_str:
        details.append(f"配管番号: {pn_str}")
    if has_water_gradient:
        dir_str = f" {nearest_wg_direction}" if nearest_wg_direction else ""
        details.append(f"水勾配: あり{dir_str} ({nearest_wg_dist:.0f}mm)")
    if nearest_slab_gradient:
        details.append(f"スラブ勾配: {nearest_slab_gradient} ({nearest_sg_dist:.0f}mm)")

    detail_str = " | ".join(details)

    # Drain sleeve with nearby gradient info → WARNING for human review
    if has_water_gradient or nearest_slab_gradient:
        return [CheckResult(
            check_id=5,
            check_name="勾配記載",
            severity="WARNING",
            sleeve=sleeve,
            message=f"排水スリーブ 勾配確認要 | {detail_str}",
            related_coords=[sleeve.center],
        )]

    if not has_fl:
        return [CheckResult(
            check_id=5,
            check_name="勾配記載",
            severity="WARNING",
            sleeve=sleeve,
            message=f"排水スリーブ FL記載なし | {detail_str}",
            related_coords=[sleeve.center],
        )]

    return [CheckResult(
        check_id=5,
        check_name="勾配記載",
        severity="OK",
        sleeve=sleeve,
        message=f"排水スリーブ | {detail_str}",
    )]


# ---------------------------------------------------------------------------
# #8 check_base_level
# ---------------------------------------------------------------------------

_RE_BASE_LEVEL = re.compile(r"\dFL\s*[＝=]", re.IGNORECASE)


def check_base_level(
    slab_labels: list[SlabLabel],
    has_base_level_def: bool = False,
) -> list[CheckResult]:
    """Check #8: base level definition exists and each slab has level info.

    Parameters
    ----------
    slab_labels:
        All SlabLabel objects extracted from F308 layers.
    has_base_level_def:
        Whether the drawing contains a base level definition
        (e.g. ``1FL＝B1FL+5150``).
    """
    results: list[CheckResult] = []

    # 1. Base level definition check
    if has_base_level_def:
        results.append(CheckResult(
            check_id=8,
            check_name="基準レベル記載",
            severity="OK",
            sleeve=None,
            message="基準レベル定義あり",
        ))
    else:
        results.append(CheckResult(
            check_id=8,
            check_name="基準レベル記載",
            severity="NG",
            sleeve=None,
            message="基準レベル（1FL等）の定義なし",
        ))

    # 2. Per-slab-number level check
    if not slab_labels:
        results.append(CheckResult(
            check_id=8,
            check_name="基準レベル記載",
            severity="NG",
            sleeve=None,
            message="スラブラベルが図面に存在しない",
        ))
        return results

    # Group by slab number
    slab_map: dict[str, list[SlabLabel]] = defaultdict(list)
    for sl in slab_labels:
        slab_map[sl.slab_no].append(sl)

    for slab_no, labels in sorted(slab_map.items()):
        has_level = any(sl.level.strip() for sl in labels)
        if has_level:
            levels = sorted({sl.level for sl in labels if sl.level.strip()})
            results.append(CheckResult(
                check_id=8,
                check_name="基準レベル記載",
                severity="OK",
                sleeve=None,
                message=f"{slab_no}: 高さ記載あり ({', '.join(levels[:3])})",
            ))
        else:
            results.append(CheckResult(
                check_id=8,
                check_name="基準レベル記載",
                severity="NG",
                sleeve=None,
                message=f"{slab_no}: 高さ記載なし",
            ))

    return results


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
        if wtype in ("RC壁", "RC", "仕上"):
            # Surface lines (RC structure / wall finish) — sleeve edge to surface
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
) -> list[CheckResult]:
    """Check #7: sleeve must not overlap with slab step lines."""
    results: list[CheckResult] = []
    radius = sleeve.diameter / 2.0

    for step in step_lines:
        dist = point_to_segment_distance(sleeve.center, step.start, step.end)
        edge_dist = dist - radius
        if edge_dist <= 0:
            results.append(CheckResult(
                check_id=7,
                check_name="段差近接",
                severity="NG",
                sleeve=sleeve,
                message=f"スリーブ端が段差線に重なっている（端から段差線まで {edge_dist:.1f}mm）",
                related_coords=[sleeve.center, step.start, step.end],
            ))

    if not results:
        results.append(CheckResult(
            check_id=7,
            check_name="段差近接",
            severity="OK",
            sleeve=sleeve,
            message="段差線との干渉なし",
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
    centre, check whether the *other* (reference-side) defpoint sits on
    a step line.  If so, the dimension is measuring FROM a step/recess
    rather than from a reliable reference — flag as NG.
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

        # Check the reference-side (non-sleeve) defpoint against step lines
        ref_pts = []
        if dp2_match:
            ref_pts.append(dim.defpoint3)  # dp2 is sleeve-side → dp3 is reference
        if dp3_match:
            ref_pts.append(dim.defpoint2)  # dp3 is sleeve-side → dp2 is reference

        for pt in ref_pts:
            if point_on_any_segment(pt, step_segs, step_tolerance):
                results.append(CheckResult(
                    check_id=10,
                    check_name="段差基準寸法",
                    severity="NG",
                    sleeve=sleeve,
                    message=f"寸法の参照点が段差線上: {pt}",
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
    sleeves: list[Sleeve],
    x_resolved: dict[str, bool] | None,
    y_resolved: dict[str, bool] | None,
) -> list[CheckResult]:
    """Check #11: sleeve dims must trace back to a grid line, not only to other sleeves."""
    results: list[CheckResult] = []
    for s in sleeves:
        x_ok = x_resolved[s.id] if x_resolved is not None else True
        y_ok = y_resolved[s.id] if y_resolved is not None else True

        if x_ok and y_ok:
            results.append(CheckResult(
                check_id=11,
                check_name="スリーブ芯寸法",
                severity="OK",
                sleeve=s,
                message="寸法チェーンが通り芯に帰着",
            ))
        else:
            missing = []
            if not x_ok:
                missing.append("X")
            if not y_ok:
                missing.append("Y")
            results.append(CheckResult(
                check_id=11,
                check_name="スリーブ芯寸法",
                severity="NG",
                sleeve=s,
                message=f"{'・'.join(missing)}方向の寸法が通り芯に帰着しない（スリーブ芯のみ）",
                related_coords=[s.center],
            ))
    return results


# ---------------------------------------------------------------------------
# #12 check_column_wall_dim
# ---------------------------------------------------------------------------

def check_column_wall_dim(
    sleeve: Sleeve,
    dims: list[DimLine],
    column_lines: list[ColumnLine],
    sleeve_tolerance: float = 50.0,
    col_tolerance: float = 5.0,
) -> list[CheckResult]:
    """Check #12: sleeve offset dims must not reference a column/wall-finish line.

    For each dimension whose defpoint2 or defpoint3 is near the sleeve
    centre, check whether the *other* (reference-side) defpoint sits on
    a column or wall-finish line.  If so, the dimension is measuring
    FROM a column/wall face rather than from a grid line — flag as NG.
    """
    if not column_lines:
        return [CheckResult(
            check_id=12,
            check_name="柱・壁仕上寸法",
            severity="OK",
            sleeve=sleeve,
            message="柱・壁仕上線なし（スキップ）",
        )]

    segments = [(c.start, c.end) for c in column_lines]
    results: list[CheckResult] = []

    for dim in dims:
        dp2_match = points_match(dim.defpoint2, sleeve.center, sleeve_tolerance)
        dp3_match = points_match(dim.defpoint3, sleeve.center, sleeve_tolerance)

        if not dp2_match and not dp3_match:
            continue

        ref_pts = []
        if dp2_match:
            ref_pts.append(dim.defpoint3)
        if dp3_match:
            ref_pts.append(dim.defpoint2)

        for pt in ref_pts:
            if point_on_any_segment(pt, segments, col_tolerance):
                results.append(CheckResult(
                    check_id=12,
                    check_name="柱・壁仕上寸法",
                    severity="NG",
                    sleeve=sleeve,
                    message=f"寸法の参照点が柱・壁仕上線上: {pt}",
                    related_coords=[pt, sleeve.center],
                ))

    if not results:
        results.append(CheckResult(
            check_id=12,
            check_name="柱・壁仕上寸法",
            severity="OK",
            sleeve=sleeve,
            message="柱・壁仕上線上の寸法基点なし",
        ))

    return results


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
    GRID_SNAP_STRICT = 5.0   # chain endpoint snapped to grid (Case A)
    GRID_SNAP_LOOSE = 300.0  # chain near grid but not snapped (Case B)
    SUM_TOLERANCE = 5.0   # mm
    GROUP_BIN = 50.0      # bin size for grouping dim line positions

    def _find_nearest_grid(
        pos: float, grid_list: list[GridLine]
    ) -> tuple[GridLine | None, float]:
        if not grid_list:
            return None, float("inf")
        best = min(grid_list, key=lambda g: abs(g.position - pos))
        return best, abs(best.position - pos)

    def _split_chain_at_grids(
        chain: list[DimLine],
        get_start: callable,
        get_end: callable,
        grid_list: list[GridLine],
    ) -> list[list[DimLine]]:
        """Split a continuous chain at grid line positions."""
        if not grid_list or len(chain) < 2:
            return [chain]

        grid_positions = sorted(g.position for g in grid_list)
        sub_chains: list[list[DimLine]] = []
        current: list[DimLine] = [chain[0]]

        for i in range(1, len(chain)):
            prev_end = get_end(chain[i - 1])
            curr_start = get_start(chain[i])
            mid = (prev_end + curr_start) / 2.0

            # Check if a grid line falls between prev dim end and curr dim start
            crossed = any(
                abs(gp - mid) < GRID_SNAP_LOOSE
                and min(prev_end, curr_start) - CHAIN_GAP < gp < max(prev_end, curr_start) + CHAIN_GAP
                for gp in grid_positions
            )

            if crossed:
                if len(current) >= 2:
                    sub_chains.append(current)
                current = [chain[i]]
            else:
                current.append(chain[i])

        if len(current) >= 2:
            sub_chains.append(current)

        return sub_chains

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

        # Build continuous chains (gap < 50mm)
        raw_chains: list[list[DimLine]] = []
        chain: list[DimLine] = [dim_group[0]]

        for i in range(1, len(dim_group)):
            prev_end = get_end(chain[-1])
            curr_start = get_start(dim_group[i])
            if abs(curr_start - prev_end) < CHAIN_GAP:
                chain.append(dim_group[i])
            else:
                if len(chain) >= 2:
                    raw_chains.append(chain)
                chain = [dim_group[i]]

        if len(chain) >= 2:
            raw_chains.append(chain)

        # Split chains at grid line positions
        chains: list[list[DimLine]] = []
        for raw in raw_chains:
            chains.extend(_split_chain_at_grids(raw, get_start, get_end, grid_list))

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

            # Skip chains too far from any grid
            if d_start > GRID_SNAP_LOOSE or d_end > GRID_SNAP_LOOSE:
                continue

            grid_span = abs(g_end.position - g_start.position)

            if axis == "X":
                coords = [(chain_start, ch[0].defpoint1[1]),
                           (chain_end, ch[-1].defpoint1[1])]
            else:
                coords = [(ch[0].defpoint1[0], chain_start),
                           (ch[-1].defpoint1[0], chain_end)]

            dim_vals = " + ".join(f"{d.measurement:.0f}" for d in ch)

            # Case B: chain near grid but not snapped
            if d_start > GRID_SNAP_STRICT or d_end > GRID_SNAP_STRICT:
                results.append(CheckResult(
                    check_id=4,
                    check_name="寸法合計",
                    severity="WARNING",
                    sleeve=None,
                    message=(
                        f"通り芯 {g_start.axis_label}–{g_end.axis_label} ({axis}) | "
                        f"寸法チェーンが通り芯にスナップしていない "
                        f"(始点差: {d_start:.0f}mm, 終点差: {d_end:.0f}mm)"
                    ),
                    related_coords=coords,
                ))
                continue

            # Case A: properly snapped — compare sum vs grid span
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
    grid_tolerance: float = 0.0,
) -> tuple[list[CheckResult], dict[str, bool] | None, dict[str, bool] | None]:
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

    x_resolved = _resolve_axis("X", v_grid_positions) if v_grid_positions else None
    y_resolved = _resolve_axis("Y", h_grid_positions) if h_grid_positions else None

    results: list[CheckResult] = []

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

    return results, x_resolved, y_resolved


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
        results.extend(check_gradient(sleeve, floor_2f.pn_labels, floor_2f.slab_zones, floor_2f.slab_labels, floor_2f.water_gradients))  # #5
        # #8 is now a global check (check_base_level), not per-sleeve
        results.extend(check_sleeve_number(sleeve))        # #14
        results.extend(check_step_slab(sleeve, floor_2f.step_lines))  # #7

        if lower_walls:
            results.extend(check_lower_wall(sleeve, lower_walls, wall_thickness))  # #6

    # --- Global level check ---
    results.extend(check_base_level(floor_2f.slab_labels, floor_2f.has_base_level_def))  # #8

    # --- Global dim checks ---
    results.extend(check_dim_sum(floor_2f.dim_lines, floor_2f.grid_lines))   # #4
    results.extend(check_dim_notation(floor_2f.dim_lines))                    # #13

    # --- Per-sleeve dim checks ---
    for sleeve in floor_2f.sleeves:
        results.extend(check_step_dim(sleeve, floor_2f.dim_lines, floor_2f.step_lines))  # #10

    # --- Per-sleeve dim checks (column/wall) ---
    for sleeve in floor_2f.sleeves:
        results.extend(check_column_wall_dim(sleeve, floor_2f.dim_lines, floor_2f.column_lines))  # #12

    # --- Position determinacy (graph-based) ---
    det_results, x_resolved, y_resolved = check_position_determinacy(
        floor_2f.sleeves, floor_2f.dim_lines, floor_2f.grid_lines,
    )
    results.extend(det_results)  # #9
    results.extend(check_sleeve_center_dim(
        floor_2f.sleeves, x_resolved, y_resolved,
    ))  # #11

    return results
