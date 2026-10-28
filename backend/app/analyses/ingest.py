"""Safe ingestion of uploaded ZIP archives.

Nothing in an archive is ever executed. Extraction is done member-by-member
with our own path validation (never ``ZipFile.extractall``) and enforces limits
on the number of members and on the bytes actually written, so a ZIP whose
headers lie about sizes cannot exhaust the disk.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.analyses.errors import APIError

_CHUNK = 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class IngestLimits:
    max_upload_bytes: int
    max_uncompressed_bytes: int
    max_members: int

    @classmethod
    def from_env(cls) -> "IngestLimits":
        return cls(
            max_upload_bytes=_env_int("ARCHLENS_MAX_UPLOAD_MB", 50) * 1024 * 1024,
            max_uncompressed_bytes=_env_int("ARCHLENS_MAX_UNCOMPRESSED_MB", 500) * 1024 * 1024,
            max_members=_env_int("ARCHLENS_MAX_ARCHIVE_FILES", 20000),
        )


def save_upload(stream: BinaryIO, dest: Path, limits: IngestLimits) -> int:
    """Copy an upload stream to ``dest``, aborting once it exceeds the size limit."""
    written = 0
    with open(dest, "wb") as out:
        while chunk := stream.read(_CHUNK):
            written += len(chunk)
            if written > limits.max_upload_bytes:
                raise APIError(
                    413,
                    "upload_too_large",
                    f"Upload exceeds the {limits.max_upload_bytes // (1024 * 1024)} MB limit.",
                )
            out.write(chunk)
    if written == 0:
        raise APIError(400, "invalid_archive", "The uploaded file is empty.")
    return written


def safe_repository_name(name: str, fallback: str = "repository") -> str:
    """Reduce an archive or folder name to a filesystem-safe directory name."""
    cleaned = _SAFE_NAME.sub("-", name).strip(".-")
    return cleaned[:100] or fallback


def _member_parts(info: zipfile.ZipInfo) -> tuple[str, ...]:
    """Validate a member name and return its path components, or raise."""
    name = info.filename
    if "\x00" in name or "\\" in name:
        raise APIError(400, "invalid_archive", f"Unsafe path in archive: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", name):
        raise APIError(400, "invalid_archive", f"Absolute path in archive: {name!r}")
    parts = tuple(p for p in path.parts if p not in ("", "."))
    if any(p == ".." for p in parts):
        raise APIError(400, "invalid_archive", f"Path traversal in archive: {name!r}")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise APIError(400, "invalid_archive", f"Symlinks are not allowed in archives: {name!r}")
    return parts


def _is_metadata(parts: tuple[str, ...]) -> bool:
    """macOS archive noise that should never be analysed."""
    return parts[0] == "__MACOSX" or parts[-1].startswith("._") or parts[-1] == ".DS_Store"


def extract_archive(archive_path: Path, dest: Path, archive_name: str, limits: IngestLimits) -> Path:
    """Extract ``archive_path`` under ``dest`` and return the repository root.

    The root is named after the archive's single top-level folder when there is
    one (``repo-main/``), else after the archive filename.
    """
    try:
        zf = zipfile.ZipFile(archive_path)
    except (zipfile.BadZipFile, OSError):
        raise APIError(400, "invalid_archive", "The upload is not a valid ZIP archive.")

    with zf:
        members: list[tuple[zipfile.ZipInfo, tuple[str, ...]]] = []
        for info in zf.infolist():
            parts = _member_parts(info)
            if not parts or _is_metadata(parts):
                continue
            members.append((info, parts))
            if len(members) > limits.max_members:
                raise APIError(
                    400, "invalid_archive", f"Archive has more than {limits.max_members} entries."
                )

        files = [(i, p) for i, p in members if not i.is_dir()]
        if not files:
            raise APIError(400, "invalid_archive", "The archive contains no files.")

        # Strip a single shared top-level folder, as GitHub "Download ZIP" produces.
        tops = {p[0] for _, p in members}
        strip = len(tops) == 1 and all(len(p) > 1 for _, p in files)
        stem = Path(archive_name).stem if archive_name else "repository"
        repo_name = safe_repository_name(next(iter(tops)) if strip else stem)

        root = (dest / repo_name).resolve()
        root.mkdir(parents=True)
        total = 0
        for info, parts in files:
            rel = parts[1:] if strip else parts
            target = root.joinpath(*rel).resolve()
            # Defence in depth: the validated parts can't escape, but verify anyway.
            if root not in target.parents:
                raise APIError(400, "invalid_archive", f"Unsafe path in archive: {info.filename!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with zf.open(info) as src, open(target, "wb") as out:
                    while chunk := src.read(_CHUNK):
                        total += len(chunk)
                        if total > limits.max_uncompressed_bytes:
                            raise APIError(
                                400,
                                "invalid_archive",
                                "Archive exceeds the "
                                f"{limits.max_uncompressed_bytes // (1024 * 1024)} MB uncompressed limit.",
                            )
                        out.write(chunk)
            except (zipfile.BadZipFile, RuntimeError, OSError, EOFError) as e:
                # RuntimeError: encrypted members; BadZipFile: CRC mismatch.
                raise APIError(400, "invalid_archive", f"Could not read {info.filename!r}: {e}")
        return root


def remove_tree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
