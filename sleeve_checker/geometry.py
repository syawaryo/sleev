import math


def point_to_segment_distance(point: tuple[float, float], seg_start: tuple[float, float], seg_end: tuple[float, float]) -> float:
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


def points_match(p1: tuple[float, float], p2: tuple[float, float], tolerance: float = 5.0) -> bool:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1]) <= tolerance


def point_on_any_segment(point: tuple[float, float], segments: list[tuple[tuple[float, float], tuple[float, float]]], tolerance: float = 5.0) -> bool:
    return any(point_to_segment_distance(point, s, e) <= tolerance for s, e in segments)
