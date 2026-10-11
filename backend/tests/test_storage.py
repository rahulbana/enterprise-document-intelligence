# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import hashlib
import io

from app.storage.local_storage import LocalStorageBackend


def test_save_returns_correct_size_and_checksum(tmp_path) -> None:
    backend = LocalStorageBackend(root=str(tmp_path))
    content = b"hello world" * 1000

    size, checksum = backend.save("key.txt", io.BytesIO(content))

    assert size == len(content)
    assert checksum == hashlib.sha256(content).hexdigest()


def test_open_returns_saved_content(tmp_path) -> None:
    backend = LocalStorageBackend(root=str(tmp_path))
    content = b"some file content"
    backend.save("key.txt", io.BytesIO(content))

    with backend.open("key.txt") as f:
        assert f.read() == content


def test_delete_removes_file(tmp_path) -> None:
    backend = LocalStorageBackend(root=str(tmp_path))
    backend.save("key.txt", io.BytesIO(b"data"))

    backend.delete("key.txt")

    assert not (tmp_path / "key.txt").exists()


def test_delete_missing_key_does_not_raise(tmp_path) -> None:
    backend = LocalStorageBackend(root=str(tmp_path))

    backend.delete("does-not-exist.txt")


def test_root_directory_is_created_on_init(tmp_path) -> None:
    root = tmp_path / "nested" / "storage"

    LocalStorageBackend(root=str(root))

    assert root.is_dir()
