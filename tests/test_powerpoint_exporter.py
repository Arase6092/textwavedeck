import pytest

from ppt.powerpoint_exporter import ExportError, _close_powerpoint, calculate_export_size


def test_calculate_export_size_for_widescreen():
    assert calculate_export_size(13.333, 7.5) == (3840, 2160)


def test_calculate_export_size_for_four_by_three():
    assert calculate_export_size(10.0, 7.5) == (3840, 2880)


@pytest.mark.parametrize("width,height", [(0, 7.5), (10, 0), (-1, 7.5)])
def test_calculate_export_size_rejects_invalid_ratio(width, height):
    with pytest.raises(ExportError, match="页面比例"):
        calculate_export_size(width, height)


def test_cleanup_quits_powerpoint_when_presentation_close_fails():
    class BrokenPresentation:
        def Close(self):
            raise RuntimeError("close failed")

    class FakePowerPoint:
        quit_called = False

        def Quit(self):
            self.quit_called = True

    powerpoint = FakePowerPoint()
    _close_powerpoint(BrokenPresentation(), powerpoint)
    assert powerpoint.quit_called
