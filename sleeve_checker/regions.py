"""FL classification for step lines via direct line-of-sight.

For each step segment we shoot a short perpendicular probe to each side,
then from the probe find the nearest FL label whose line-of-sight is not
blocked by any OTHER step chain. Segments that share endpoints belong to
the same chain (the two sides of one contiguous slab boundary) and are
transparent to each other so they don't mutually block probes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import SlabZone, StepLine


_PROBE_OFFSET = 20.0          # mm — how far off the segment to place the probe
_ENDPOINT_TOL = 5.0           # mm — endpoints within this distance are treated as shared


@dataclass
class StepClassification:
    segment: StepLine
    side_a_fl: int | None
    side_b_fl: int | None
    status: str  # "real" | "spurious" | "unknown"


def _perp_unit(seg_start, seg_end) -> tuple[float, float]:
    dx = seg_end[0] - seg_start[0]
    dy = seg_end[1] - seg_start[1]
    n = (dx * dx + dy * dy) ** 0.5
    if n == 0:
        return (0.0, 0.0)
    return (-dy / n, dx / n)


def _segments_intersect(
    a1: tuple[float, float], a2: tuple[float, float],
    b1: tuple[float, float], b2: tuple[float, float],
) -> bool:
    def _orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        if abs(v) < 1e-9:
            return 0
        return 1 if v > 0 else -1
    o1 = _orient(a1, a2, b1); o2 = _orient(a1, a2, b2)
    o3 = _orient(b1, b2, a1); o4 = _orient(b1, b2, a2)
    return o1 != o2 and o3 != o4 and o1 != 0 and o3 != 0


def _chain_groups(step_lines: Sequence[StepLine]) -> list[int]:
    """Return list parallel to step_lines giving each seg's chain id (union-find by shared endpoints)."""
    n = len(step_lines)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b

    tol2 = _ENDPOINT_TOL ** 2

    def close(p, q) -> bool:
        dx = p[0] - q[0]; dy = p[1] - q[1]
        return dx * dx + dy * dy <= tol2

    for i in range(n):
        for j in range(i + 1, n):
            si, sj = step_lines[i], step_lines[j]
            if (close(si.start, sj.start) or close(si.start, sj.end)
                    or close(si.end, sj.start) or close(si.end, sj.end)):
                union(i, j)

    return [find(i) for i in range(n)]


def _nearest_unblocked_label(
    origin: tuple[float, float],
    side_sign: int,
    perp: tuple[float, float],
    fl_labels: Sequence[SlabZone],
    step_segs: list[tuple[tuple[float, float], tuple[float, float]]],
    blocker_indices: range,
    own_chain: int,
    chain_of: list[int],
) -> int | None:
    best_dist = float("inf")
    best_fl: int | None = None
    nx, ny = perp
    for lab in fl_labels:
        dx = lab.x - origin[0]; dy = lab.y - origin[1]
        if (dx * nx + dy * ny) * side_sign <= 0:
            continue
        d = (dx * dx + dy * dy) ** 0.5
        if d >= best_dist:
            continue
        # Line-of-sight: ignore segments in our own step chain.
        blocked = False
        for k in blocker_indices:
            if chain_of[k] == own_chain:
                continue
            a, b = step_segs[k]
            if _segments_intersect(origin, (lab.x, lab.y), a, b):
                blocked = True
                break
        if not blocked:
            best_dist = d
            best_fl = lab.fl_value
    return best_fl


def classify_step_segments(
    step_lines: Sequence[StepLine],
    fl_labels: Sequence[SlabZone],
) -> list[StepClassification]:
    segs = [(s.start, s.end) for s in step_lines]
    chain_of = _chain_groups(step_lines)
    idx_range = range(len(segs))
    out: list[StepClassification] = []

    for i, s in enumerate(step_lines):
        nx, ny = _perp_unit(s.start, s.end)
        if nx == 0 and ny == 0:
            out.append(StepClassification(s, None, None, "unknown"))
            continue
        mx = (s.start[0] + s.end[0]) / 2
        my = (s.start[1] + s.end[1]) / 2
        origin_a = (mx + nx * _PROBE_OFFSET, my + ny * _PROBE_OFFSET)
        origin_b = (mx - nx * _PROBE_OFFSET, my - ny * _PROBE_OFFSET)
        fl_a = _nearest_unblocked_label(origin_a, +1, (nx, ny), fl_labels,
                                        segs, idx_range, chain_of[i], chain_of)
        fl_b = _nearest_unblocked_label(origin_b, -1, (nx, ny), fl_labels,
                                        segs, idx_range, chain_of[i], chain_of)
        if fl_a is None or fl_b is None:
            status = "unknown"
        elif fl_a != fl_b:
            status = "real"
        else:
            status = "spurious"
        out.append(StepClassification(s, fl_a, fl_b, status))
    return out
