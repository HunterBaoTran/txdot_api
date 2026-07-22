from __future__ import annotations

from collections.abc import Sequence

Point = tuple[float, float]


def polygon_area(points: Sequence[Point]) -> float:
    return (
        abs(
            sum(
                x1 * y2 - x2 * y1
                for (x1, y1), (x2, y2) in zip(points, (*points[1:], points[0]), strict=True)
            )
        )
        / 2
    )


def polygon_self_intersects(points: Sequence[Point]) -> bool:
    edge_count = len(points)
    for first in range(edge_count):
        a1, a2 = points[first], points[(first + 1) % edge_count]
        for second in range(first + 1, edge_count):
            if second in {first, (first + 1) % edge_count}:
                continue
            if first == 0 and second == edge_count - 1:
                continue
            b1, b2 = points[second], points[(second + 1) % edge_count]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    def orientation(p: Point, q: Point, r: Point) -> float:
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    first = orientation(a, b, c)
    second = orientation(a, b, d)
    third = orientation(c, d, a)
    fourth = orientation(c, d, b)
    return first * second < 0 and third * fourth < 0
