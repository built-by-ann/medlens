import json
import logging
import time
from pathlib import Path

from app.storage.base import ObjectNotFoundError, StorageError, StorageService, StoredObject

logger = logging.getLogger(__name__)


class LocalStorageService(StorageService):
    """Stores objects as plain files under a local directory - the default
    backend (Settings.storage_backend == "local"), so the application, its
    tests, and CI all work with zero AWS configuration. `key` is used
    directly as a path relative to `base_dir`; a key containing "/" (the
    convention app/services/clinical_document_service.py's key generation
    uses, e.g. "clinical-documents/{patient_id}/...") simply becomes a
    subdirectory, which upload() creates as needed.

    Content type isn't a first-class concept in a plain filesystem, so it's
    written to a small sidecar `<key>.meta.json` file next to the content
    and read back on download() - the equivalent of what S3 stores as
    object metadata for free.
    """

    def __init__(self, base_dir: str):
        self._base_dir = Path(base_dir)

    def _content_path(self, key: str) -> Path:
        return self._base_dir / key

    def _meta_path(self, key: str) -> Path:
        return self._base_dir / f"{key}.meta.json"

    def upload(self, key: str, content: bytes, content_type: str) -> None:
        content_path = self._content_path(key)
        started_at = time.monotonic()

        try:
            content_path.parent.mkdir(parents=True, exist_ok=True)
            content_path.write_bytes(content)
            self._meta_path(key).write_text(json.dumps({"content_type": content_type}))
        except OSError as error:
            raise StorageError(f"Failed to write local object: {key}") from error

        logger.info(
            "Local storage upload completed",
            extra={
                "event": "storage_upload_completed",
                "storage_backend": "local",
                "storage_key": key,
                "duration_ms": round((time.monotonic() - started_at) * 1000, 1),
            },
        )

    def download(self, key: str) -> StoredObject:
        content_path = self._content_path(key)

        if not content_path.is_file():
            raise ObjectNotFoundError(f"No local object at key: {key}")

        try:
            content = content_path.read_bytes()
            meta_path = self._meta_path(key)
            content_type = (
                json.loads(meta_path.read_text())["content_type"]
                if meta_path.is_file()
                else "application/octet-stream"
            )
        except OSError as error:
            raise StorageError(f"Failed to read local object: {key}") from error

        return StoredObject(content=content, content_type=content_type)

    def delete(self, key: str) -> None:
        content_path = self._content_path(key)

        if not content_path.is_file():
            raise ObjectNotFoundError(f"No local object at key: {key}")

        try:
            content_path.unlink()
            self._meta_path(key).unlink(missing_ok=True)
        except OSError as error:
            raise StorageError(f"Failed to delete local object: {key}") from error
