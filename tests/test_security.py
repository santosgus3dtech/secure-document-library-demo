from pathlib import Path

import pytest

from app.security import safe_document_path, validate_pdf_name


def test_valid_pdf_name_stays_inside_root(tmp_path: Path):
    assert safe_document_path(tmp_path, "security-baseline.pdf") == tmp_path / "security-baseline.pdf"


@pytest.mark.parametrize("name", ["../secret.pdf", "folder/file.pdf", "file.txt", ".pdf"])
def test_unsafe_names_are_rejected(name: str):
    with pytest.raises(ValueError):
        validate_pdf_name(name)
