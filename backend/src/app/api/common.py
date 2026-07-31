"""Small pieces shared by more than one router.

Kept deliberately tiny: this is not a dumping ground for anything
API-related, only for genuine duplication between two or more routers.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from app.infrastructure.filesystem.artifact_store import ExportedFileNotFoundError


@contextmanager
def translate_to_404(detail: str) -> Iterator[None]:
    """Turn a store lookup failure into a 404, with one message for the caller.

    `IncidentArtifactStore` raises `ExportedFileNotFoundError` for a
    missing file and `ValueError` for a malformed `incident_id` (see
    `_validate_path_component`); both mean the same thing to an API
    caller -- there's nothing at that id -- so both collapse to the same
    404 rather than a 404 for one and a 500 for the other.
    """
    try:
        yield
    except (ExportedFileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=detail) from exc
