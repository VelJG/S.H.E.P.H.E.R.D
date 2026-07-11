from __future__ import annotations

from collections.abc import Sequence


Point = tuple[float, float]


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Return whether a point is inside a zone polygon."""
    if len(polygon) < 3:
        return False

    x, y = point
    inside = False
    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        if (current_y > y) != (previous_y > y):
            edge_x = (previous_x - current_x) * (y - current_y) / (previous_y - current_y) + current_x
            if x < edge_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


if __name__ == "__main__":
    assert point_in_polygon((5, 5), [(0, 0), (10, 0), (10, 10), (0, 10)])
    assert not point_in_polygon((15, 5), [(0, 0), (10, 0), (10, 10), (0, 10)])
    print("zone self-check: ok")
