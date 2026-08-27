"""Read-only attachment inventory.

Run from ``backend`` with ``DATABASE_URL`` and, where appropriate,
``FILE_STORAGE_ROOT`` configured. It never changes database rows or files.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.storage import resolve_stored_path, storage_root
from app.db.database import SessionLocal
from app.models.models import InvoiceFile


def main() -> int:
    root = storage_root()
    db = SessionLocal()
    try:
        rows = db.query(InvoiceFile).all()
        present, missing, expected_paths = [], [], set()
        for row in rows:
            try:
                path = resolve_stored_path(row.stored_path)
            except ValueError as exc:
                missing.append((row.id, row.stored_path, f"invalid key: {exc}"))
                continue
            expected_paths.add(path.resolve())
            if path.is_file():
                present.append((row.id, path))
            else:
                missing.append((row.id, row.stored_path, "file not found"))

        physical = set()
        folders = {root / "invoices", root / "credit_notes"}
        legacy_root = Path("storage")
        if legacy_root.resolve() != root.resolve():
            folders.update({legacy_root / "invoices", legacy_root / "credit_notes"})
        for folder in folders:
            if folder.is_dir():
                physical.update(path.resolve() for path in folder.rglob("*") if path.is_file())
        orphaned = sorted(physical - expected_paths)

        print(f"storage_root={root}")
        print(f"database_file_rows={len(rows)}")
        print(f"present={len(present)}")
        print(f"missing={len(missing)}")
        print(f"orphaned_physical_files={len(orphaned)}")
        for file_id, stored_path, reason in missing:
            print(f"MISSING file_id={file_id} key={stored_path} reason={reason}")
        for path in orphaned:
            print(f"ORPHAN path={path}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
