import os
import tempfile
import unittest
from pathlib import Path

from app.core import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_root = os.environ.get(storage.FILE_STORAGE_ROOT_ENV)
        os.environ[storage.FILE_STORAGE_ROOT_ENV] = str(Path(self.temp_dir.name) / "persistent")

    def tearDown(self):
        if self.original_root is None:
            os.environ.pop(storage.FILE_STORAGE_ROOT_ENV, None)
        else:
            os.environ[storage.FILE_STORAGE_ROOT_ENV] = self.original_root
        self.temp_dir.cleanup()

    def test_write_uses_portable_key_under_configured_root(self):
        storage.ensure_storage_ready()
        key, path = storage.write_upload("invoice", "abc.pdf", b"invoice")

        self.assertEqual(key, "invoices/abc.pdf")
        self.assertEqual(path, storage.storage_root() / "invoices" / "abc.pdf")
        self.assertEqual(path.read_bytes(), b"invoice")
        self.assertEqual(storage.resolve_stored_path(key), path)

    def test_existing_legacy_relative_path_is_readable(self):
        original_cwd = Path.cwd()
        working_dir = Path(self.temp_dir.name) / "legacy-working-directory"
        legacy_file = working_dir / "storage" / "invoices" / "historic.pdf"
        legacy_file.parent.mkdir(parents=True)
        legacy_file.write_bytes(b"historic")
        os.chdir(working_dir)
        try:
            self.assertEqual(
                storage.resolve_stored_path("storage/invoices/historic.pdf"),
                Path("storage/invoices/historic.pdf"),
            )
        finally:
            os.chdir(original_cwd)

    def test_production_requires_explicit_storage_root(self):
        os.environ.pop(storage.FILE_STORAGE_ROOT_ENV, None)
        original_env = os.environ.get("ENV")
        os.environ["ENV"] = "production"
        try:
            with self.assertRaisesRegex(RuntimeError, "FILE_STORAGE_ROOT"):
                storage.storage_root()
        finally:
            if original_env is None:
                os.environ.pop("ENV", None)
            else:
                os.environ["ENV"] = original_env


if __name__ == "__main__":
    unittest.main()
