import hashlib
from io import BytesIO
from pathlib import Path

import pytest

from scripts.materialize_lfs_data import materialize_file, read_lfs_pointer


class FakeResponse(BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _pointer(content: bytes) -> bytes:
    digest = hashlib.sha256(content).hexdigest()
    return (
        b"version https://git-lfs.github.com/spec/v1\n"
        + f"oid sha256:{digest}\nsize {len(content)}\n".encode()
    )


def test_read_lfs_pointer_returns_none_for_materialized_data(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    path.write_bytes(b'{"real": true}\n')

    assert read_lfs_pointer(path) is None


def test_materialize_file_downloads_and_verifies_the_exact_lfs_object(tmp_path: Path) -> None:
    content = b'{"row": 1}\n{"row": 2}\n'
    path = tmp_path / "data.jsonl"
    path.write_bytes(_pointer(content))
    requests: list[tuple[str, int]] = []

    def opener(request, *, timeout: int):  # type: ignore[no-untyped-def]
        requests.append((request.full_url, timeout))
        return FakeResponse(content)

    changed = materialize_file(
        path,
        repo_owner="owner",
        repo_name="repo",
        commit_sha="abc123",
        repository_path="data/filtered/data.jsonl",
        opener=opener,
    )

    assert changed is True
    assert path.read_bytes() == content
    assert requests == [
        (
            "https://media.githubusercontent.com/media/owner/repo/abc123/data/filtered/data.jsonl",
            600,
        )
    ]
    assert not path.with_name("data.jsonl.lfs-download").exists()


def test_materialize_file_rejects_content_that_does_not_match_pointer(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    pointer = _pointer(b"expected")
    path.write_bytes(pointer)

    with pytest.raises(RuntimeError, match="verification failed"):
        materialize_file(
            path,
            repo_owner="owner",
            repo_name="repo",
            commit_sha="abc123",
            repository_path="data/filtered/data.jsonl",
            opener=lambda *_args, **_kwargs: FakeResponse(b"wrong"),
        )

    assert path.read_bytes() == pointer
    assert not path.with_name("data.jsonl.lfs-download").exists()
