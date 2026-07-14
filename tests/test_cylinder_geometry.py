import pytest

from widgets import cylinder_geometry
from widgets.cylinder_geometry import cylinder_pose, inertia_target, snap_index


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
    assert cylinder_pose(2.0).visible
    assert not cylinder_pose(3.0).visible


def test_five_page_layers_have_distinct_depth():
    center = cylinder_pose(0.0)
    first = cylinder_pose(1.0)
    second = cylinder_pose(2.0)
    assert center.opacity == 1.0
    assert first.opacity == pytest.approx(0.58)
    assert second.opacity == pytest.approx(0.18)
    assert center.scale > first.scale > second.scale


def test_carousel_viewport_geometry_matches_approved_density():
    """共享舞台参数应匹配已确认的桌面和紧凑窗口密度。"""
    desktop = cylinder_geometry.carousel_viewport_geometry(1440, 900)
    compact = cylinder_geometry.carousel_viewport_geometry(1024, 768)

    assert desktop.target_height == pytest.approx(603.0)
    assert desktop.max_page_width == pytest.approx(1238.4)
    assert desktop.radius == pytest.approx(660.0)
    assert desktop.center_y == pytest.approx(446.0)
    assert desktop.depth_drop == pytest.approx(92.0)
    assert compact.target_height == pytest.approx(514.56)
    assert compact.radius == pytest.approx(501.76)


def test_fit_carousel_page_caps_wide_slides_without_distortion():
    """宽屏页面在窄窗口受宽度限制，且始终保持原始比例。"""
    desktop = cylinder_geometry.carousel_viewport_geometry(1440, 900)
    compact = cylinder_geometry.carousel_viewport_geometry(1024, 768)

    assert cylinder_geometry.fit_carousel_page(desktop, 16 / 9) == pytest.approx((1072.0, 603.0))
    assert cylinder_geometry.fit_carousel_page(compact, 16 / 9) == pytest.approx((880.64, 495.36))
    assert cylinder_geometry.fit_carousel_page(compact, 4 / 3) == pytest.approx((686.08, 514.56))


@pytest.mark.parametrize(
    "offset,velocity,page_count,expected",
    [(5.1, 1.0, 20, 7), (5.1, -1.0, 20, 3), (0.1, -2.0, 20, 0), (18.9, 2.0, 20, 19)],
)
def test_inertia_target_never_skips_more_than_two_pages(offset, velocity, page_count, expected):
    assert inertia_target(offset, velocity, page_count) == expected


@pytest.mark.parametrize(
    "offset,page_count,expected",
    [(-0.7, 5, 0), (0.49, 5, 0), (0.5, 5, 1), (2.6, 5, 3), (8.0, 5, 4), (2.0, 0, 0)],
)
def test_snap_index_clamps_to_page_boundaries(offset, page_count, expected):
    assert snap_index(offset, page_count) == expected
