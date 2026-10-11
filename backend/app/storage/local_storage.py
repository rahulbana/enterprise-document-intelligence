# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Local-disk StorageBackend. Root directory comes from
# Settings.LOCAL_STORAGE_PATH; swapping to S3/GCS later means adding a new
# StorageBackend implementation, not touching any caller of this interface.

import hashlib
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.storage.base import StorageBackend

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: str | None = None) -> None:
        self._root = Path(root or settings.LOCAL_STORAGE_PATH)
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, file: BinaryIO) -> tuple[int, str]:
        target = self._path_for(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        size = 0
        with target.open("wb") as out:
            while chunk := file.read(_CHUNK_SIZE):
                out.write(chunk)
                hasher.update(chunk)
                size += len(chunk)

        return size, hasher.hexdigest()

    def open(self, key: str) -> BinaryIO:
        return self._path_for(key).open("rb")

    def delete(self, key: str) -> None:
        self._path_for(key).unlink(missing_ok=True)

    def _path_for(self, key: str) -> Path:
        return self._root / key
