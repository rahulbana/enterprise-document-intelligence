# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Picks the configured StorageBackend implementation. Cached so local disk
# setup (creating the root directory) happens once per process.

from functools import lru_cache

from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.local_storage import LocalStorageBackend

_BACKENDS: dict[str, type[StorageBackend]] = {
    "local": LocalStorageBackend,
}


@lru_cache
def get_storage_backend() -> StorageBackend:
    backend_cls = _BACKENDS.get(settings.STORAGE_BACKEND)
    if backend_cls is None:
        valid = ", ".join(sorted(_BACKENDS))
        raise ValueError(
            f"Unknown STORAGE_BACKEND '{settings.STORAGE_BACKEND}'. Valid options: {valid}"
        )
    return backend_cls()
