from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def source_content_sha256(path: Path) -> str:
    stat = path.stat()
    verified_sha256 = _read_verified_identity(path, stat.st_size)
    if verified_sha256 is not None:
        return verified_sha256
    return _hash_file(str(path.resolve()), stat.st_size, stat.st_mtime_ns)


def write_verified_content_identity(path: Path, *, sha256: str, size: int) -> None:
    if not SHA256_PATTERN.fullmatch(sha256) or size < 0:
        raise ValueError("A verified content identity requires a SHA-256 digest and non-negative size")
    if path.stat().st_size != size:
        raise RuntimeError(f"Verified content identity size does not match source file: {path}")
    identity_path = _identity_path(path)
    temporary_path = identity_path.with_suffix(identity_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps({"sha256": sha256, "size": size}, sort_keys=True),
        encoding="utf-8",
    )
    temporary_path.replace(identity_path)


def remove_verified_content_identity(path: Path) -> None:
    _identity_path(path).unlink(missing_ok=True)


def _read_verified_identity(path: Path, size: int) -> str | None:
    try:
        value = json.loads(_identity_path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("size") != size:
        return None
    sha256 = value.get("sha256")
    return sha256 if isinstance(sha256, str) and SHA256_PATTERN.fullmatch(sha256) else None


@lru_cache(maxsize=16)
def _hash_file(path_value: str, size: int, mtime_ns: int) -> str:
    del size, mtime_ns
    digest = hashlib.sha256()
    with Path(path_value).open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _identity_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.source-identity.json")
