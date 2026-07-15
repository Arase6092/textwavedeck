from pathlib import Path

from app.runtime_paths import bundle_path, project_root


def test_project_root_points_to_repo_root_in_source_mode():
    root = project_root()
    assert root.name == "手势控制PPT"
    assert (root / "main.py").exists()


def test_bundle_path_joins_relative_parts():
    path = bundle_path("resources", "branding", "wavedeck.ico")
    assert isinstance(path, Path)
    assert path.name == "wavedeck.ico"
