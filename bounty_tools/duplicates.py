from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_duplicates(
    root: str | Path,
    min_size: int = 0,
) -> list[dict[str, object]]:
    root_path = Path(root).expanduser()
    if not root_path.exists():
        raise FileNotFoundError(f"Scan path does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Scan path is not a directory: {root_path}")

    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in _iter_regular_files(root_path):
        try:
            size = path.stat().st_size
        except (FileNotFoundError, PermissionError, OSError):
            continue
        if size >= min_size:
            by_size[size].append(path)

    groups: list[dict[str, object]] = []
    for size, candidates in sorted(by_size.items()):
        if len(candidates) < 2:
            continue

        by_hash: dict[str, list[Path]] = defaultdict(list)
        for path in candidates:
            try:
                by_hash[sha256_file(path)].append(path)
            except (FileNotFoundError, PermissionError, OSError):
                continue

        for digest, paths in sorted(by_hash.items()):
            if len(paths) > 1:
                groups.append(
                    {
                        "sha256": digest,
                        "size": size,
                        "count": len(paths),
                        "paths": sorted(str(path) for path in paths),
                    }
                )

    return sorted(
        groups,
        key=lambda group: (
            str(group["paths"][0]),
            str(group["sha256"]),
        ),
    )


def _iter_regular_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        try:
            if path.is_file():
                yield path
        except (PermissionError, OSError):
            continue
