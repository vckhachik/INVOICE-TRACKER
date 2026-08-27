"""Storage helpers for invoice and credit-note attachments.

Database rows store portable file keys (for example ``invoices/<hash>.pdf``),
never deployment-specific absolute paths. The storage root is selected by the
``FILE_STORAGE_ROOT`` environment variable.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath
from uuid import uuid4


FILE_STORAGE_ROOT_ENV = "FILE_STORAGE_ROOT"
DOCUMENT_FOLDERS = {"invoice": "invoices", "credit_note": "credit_notes"}


def storage_root() -> Path:
    """Return the configured root; local development defaults to ``storage``."""
    configured_root = os.getenv(FILE_STORAGE_ROOT_ENV)
    if configured_root:
        return Path(configured_root).expanduser()
    if os.getenv("ENV", "development").lower() == "production":
        raise RuntimeError(f"{FILE_STORAGE_ROOT_ENV} is required in production")
    return Path("storage")


def document_directory(document_type: str) -> Path:
    try:
        return storage_root() / DOCUMENT_FOLDERS[document_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported document type: {document_type}") from exc


def ensure_storage_ready() -> dict[str, Path]:
    """Create required directories and fail startup when the root is not writable."""
    root = storage_root()
    root.mkdir(parents=True, exist_ok=True)
    directories = {name: document_directory(name) for name in DOCUMENT_FOLDERS}
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".storage-check-", delete=True):
            pass
    except OSError as exc:
        raise RuntimeError(f"File storage is not writable: {root}") from exc

    return directories


def make_file_key(document_type: str, filename: str) -> str:
    if not filename or Path(filename).name != filename:
        raise ValueError("Filename must not include a path")
    return f"{DOCUMENT_FOLDERS[document_type]}/{filename}"


def _safe_relative_key(value: str) -> PurePosixPath:
    key = PurePosixPath(value.replace("\\", "/"))
    if key.is_absolute() or ".." in key.parts:
        raise ValueError("Stored file key must be a relative path")
    return key


def resolve_stored_path(stored_path: str) -> Path:
    """Resolve new keys and legacy relative paths without changing database rows.

    Existing values beginning with ``storage/`` are checked at their old
    process-relative location first; otherwise they resolve under the configured
    persistent root. This preserves read compatibility during a safe transition.
    """
    if not stored_path:
        raise ValueError("Stored file path is missing")

    raw = Path(stored_path)
    if raw.is_absolute():
        return raw

    key = _safe_relative_key(stored_path)
    if key.parts and key.parts[0] == "storage":
        legacy_path = Path(stored_path)
        if legacy_path.exists():
            return legacy_path
        key = PurePosixPath(*key.parts[1:])

    resolved = storage_root() / Path(*key.parts)
    root_resolved = storage_root().resolve()
    if not resolved.resolve().is_relative_to(root_resolved):
        raise ValueError("Stored file key resolves outside configured storage")
    return resolved


def write_upload(document_type: str, filename: str, contents: bytes) -> tuple[str, Path]:
    """Atomically write an upload and return its database key plus full path."""
    directory = document_directory(document_type)
    directory.mkdir(parents=True, exist_ok=True)
    file_key = make_file_key(document_type, filename)
    destination = resolve_stored_path(file_key)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.upload")

    try:
        with open(temporary, "wb") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        if not destination.is_file():
            raise OSError(f"Uploaded file was not written: {destination}")
        return file_key, destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def delete_stored_file(stored_path: str) -> None:
    """Best-effort removal used only after a successful database delete."""
    resolve_stored_path(stored_path).unlink(missing_ok=True)
