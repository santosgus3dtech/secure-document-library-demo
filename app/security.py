from pathlib import Path
import re


SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}\.pdf$", re.IGNORECASE)


def validate_pdf_name(filename: str) -> str:
    if not SAFE_NAME.fullmatch(filename) or Path(filename).name != filename:
        raise ValueError("Invalid PDF filename")
    return filename


def safe_document_path(root: Path, filename: str) -> Path:
    validate_pdf_name(filename)
    root = root.resolve()
    candidate = (root / filename).resolve()
    if candidate.parent != root:
        raise ValueError("Document path escapes storage root")
    return candidate
