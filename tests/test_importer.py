from pathlib import Path

import pytest

from ppt.importer import ImportErrorMessage, PPTImporter


def test_importer_rejects_missing_and_unsupported_files(tmp_path):
    importer = PPTImporter(cache_base=tmp_path / "projects")
    with pytest.raises(ImportErrorMessage, match="文件不存在"):
        importer.validate_source(tmp_path / "missing.pptx")
    unsupported = tmp_path / "notes.pdf"
    unsupported.write_bytes(b"pdf")
    with pytest.raises(ImportErrorMessage, match="仅支持"):
        importer.validate_source(unsupported)
