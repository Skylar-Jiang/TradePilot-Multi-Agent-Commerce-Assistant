from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote
from urllib.request import Request, urlopen

LFS_VERSION = "version https://git-lfs.github.com/spec/v1"
LFS_FILES = (
    "data/filtered/meta_pet_supplies_prefiltered.jsonl",
    "data/filtered/pet_supplies_reviews_prefiltered.jsonl",
)
OID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
Opener = Callable[..., BinaryIO]


@dataclass(frozen=True)
class LfsPointer:
    sha256: str
    size: int


def read_lfs_pointer(path: Path) -> LfsPointer | None:
    with path.open("rb") as source:
        prefix = source.read(256)
    try:
        lines = prefix.decode("ascii").splitlines()
    except UnicodeDecodeError:
        return None
    if not lines or lines[0] != LFS_VERSION:
        return None
    values = dict(line.split(" ", 1) for line in lines[1:] if " " in line)
    oid = values.get("oid", "")
    size = values.get("size", "")
    if not oid.startswith("sha256:") or not size.isdigit():
        raise RuntimeError(f"Invalid Git LFS pointer: {path}")
    digest = oid.removeprefix("sha256:")
    if not OID_PATTERN.fullmatch(digest):
        raise RuntimeError(f"Invalid Git LFS SHA-256: {path}")
    return LfsPointer(sha256=digest, size=int(size))


def materialize_file(
    path: Path,
    *,
    repo_owner: str,
    repo_name: str,
    commit_sha: str,
    repository_path: str,
    opener: Opener = urlopen,
) -> bool:
    pointer = read_lfs_pointer(path)
    if pointer is None:
        return False
    parts = [repo_owner, repo_name, commit_sha, *repository_path.split("/")]
    url = "https://media.githubusercontent.com/media/" + "/".join(
        quote(part, safe="") for part in parts
    )
    request = Request(url, headers={"User-Agent": "TradePilot-Railway-LFS/1.0"})
    temporary = path.with_name(f"{path.name}.lfs-download")
    digest = hashlib.sha256()
    downloaded = 0
    try:
        with opener(request, timeout=600) as response, temporary.open("wb") as destination:
            while chunk := response.read(1024 * 1024):
                destination.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
        if downloaded != pointer.size or digest.hexdigest() != pointer.sha256:
            raise RuntimeError(
                f"Git LFS verification failed for {repository_path}: "
                f"expected size={pointer.size}, downloaded size={downloaded}"
            )
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return True


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    pending = [relative for relative in LFS_FILES if read_lfs_pointer(root / relative) is not None]
    if not pending:
        print("Git LFS data already materialized; build download skipped")
        return

    variables = {
        "repo_owner": os.getenv("RAILWAY_GIT_REPO_OWNER", "").strip(),
        "repo_name": os.getenv("RAILWAY_GIT_REPO_NAME", "").strip(),
        "commit_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA", "").strip(),
    }
    missing = [name for name, value in variables.items() if not value]
    if missing:
        raise RuntimeError(
            "Git LFS pointers require Railway Git build variables: " + ", ".join(missing)
        )

    for relative in pending:
        changed = materialize_file(
            root / relative,
            repository_path=relative,
            **variables,
        )
        if changed:
            print(f"Materialized and verified Git LFS data: {relative}")


if __name__ == "__main__":
    main()
