import pytest

from widgets.cylinder_geometry import cylinder_pose, snap_index


def test_center_page_is_front_facing_and_largest():
    center = cylinder_pose(0.0)
    side = cylinder_pose(1.0)
    assert center.x_factor == 0.0
    assert center.scale == 1.0
    assert center.horizontal_scale == 1.0
    assert center.opacity == 1.0
    assert abs(side.x_factor) > 0
    assert side.scale < center.scale
    assert side.opacity < center.opacity


def test_pose_is_symmetric():
    left = cylinder_pose(-1.0)
    right = cylinder_pose(1.0)
    assert left.x_factor == pytest.approx(-right.x_factor)
    assert left.scale == pytest.approx(right.scale)
    assert left.horizontal_scale == pytest.approx(right.horizontal_scale)
    assert left.opacity == pytest.approx(right.opacity)


def test_distant_pages_are_hidden():
    assert cylinder_pose(3.0).visible
    assert not cylinder_pose(4.0).visible


@pytest.mark.parametrize(
    "offset,page_count,expected",
    [(-0.7, 5, 0), (0.49, 5, 0), (0.5, 5, 1), (2.6, 5, 3), (8.0, 5, 4), (2.0, 0, 0)],
)
def test_snap_index_clamps_to_page_boundaries(offset, page_count, expected):
    assert snap_index(offset, page_count) == expected
