import pytest

from ppt.powerpoint_exporter import ExportError, calculate_export_size


def test_calculate_export_size_for_widescreen():
    assert calculate_export_size(13.333, 7.5) == (3840, 2160)


def test_calculate_export_size_for_four_by_three():
    assert calculate_export_size(10.0, 7.5) == (3840, 2880)


@pytest.mark.parametrize("width,height", [(0, 7.5), (10, 0), (-1, 7.5)])
def test_calculate_export_size_rejects_invalid_ratio(width, height):
    with pytest.raises(ExportError, match="页面比例"):
        calculate_export_size(width, height)
