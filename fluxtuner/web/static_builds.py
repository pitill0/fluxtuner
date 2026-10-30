"""Persistent, content-addressed snapshots of Web static assets."""

from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

MANIFEST_NAME = ".fluxtuner-manifest.json"
BUILD_ID_LENGTH = 16
STALE_TEMP_SECONDS = 3600


class StaticBuildError(RuntimeError):
    """A static snapshot could not be built or verified."""


@dataclass(frozen=True)
class StaticBuild:
    build_id: str
    directory: Path


def _regular_file(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISREG(info.st_mode)


def _inventory(source: Path, *, exclude_manifest: bool = False) -> dict[str, str]:
    """Hash a regular-file tree; reject symlinks and special files."""
    if source.is_symlink() or not source.is_dir():
        raise StaticBuildError("Static source is not a regular directory")

    files: dict[str, str] = {}

    for directory, subdirs, names in os.walk(source, followlinks=False):
        base = Path(directory)

        for dirname in subdirs:
            candidate = base / dirname
            if candidate.is_symlink() or not candidate.is_dir():
                raise StaticBuildError(f"Unsafe static directory: {candidate}")

        for name in names:
            candidate = base / name

            if not _regular_file(candidate):
                raise StaticBuildError(f"Unsafe static file: {candidate}")

            relative = candidate.relative_to(source).as_posix()
            if relative == MANIFEST_NAME:
                if exclude_manifest:
                    continue
                raise StaticBuildError("Reserved manifest filename in source")

            files[relative] = hashlib.sha256(candidate.read_bytes()).hexdigest()

    if not files:
        raise StaticBuildError("Static source is empty")

    return dict(sorted(files.items()))


def _manifest_bytes(files: dict[str, str]) -> bytes:
    return (
        json.dumps(
            {"format": 1, "files": files},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _manifest_id(manifest: bytes) -> str:
    return hashlib.sha256(manifest).hexdigest()[:BUILD_ID_LENGTH]


def verify_static_snapshot(directory: Path, build_id: str) -> bool:
    """Verify complete snapshot contents against the published manifest."""
    try:
        if (
            len(build_id) != BUILD_ID_LENGTH
            or any(character not in "0123456789abcdef" for character in build_id)
            or directory.is_symlink()
            or not directory.is_dir()
        ):
            return False

        manifest_path = directory / MANIFEST_NAME
        if not _regular_file(manifest_path):
            return False

        raw = manifest_path.read_bytes()
        if _manifest_id(raw) != build_id:
            return False

        parsed = json.loads(raw)
        if parsed.get("format") != 1 or not isinstance(parsed.get("files"), dict):
            return False

        expected = parsed["files"]
        actual = _inventory_without_manifest(directory)
        return actual == expected
    except (OSError, ValueError, TypeError, StaticBuildError):
        return False


def _inventory_without_manifest(directory: Path) -> dict[str, str]:
    return _inventory(directory, exclude_manifest=True)


def _reject_symlink_components(path: Path) -> None:
    """Reject symbolic links anywhere in an absolute storage path."""
    absolute = path.absolute()
    for component in (*reversed(absolute.parents), absolute):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise StaticBuildError(f"Cannot inspect snapshot storage path: {component}") from exc

        if stat.S_ISLNK(info.st_mode):
            raise StaticBuildError(f"Symbolic link in snapshot storage path: {component}")


@contextmanager
def _publication_lock(root: Path) -> Iterator[None]:
    lock_path = root / ".publish.lock"
    descriptor = os.open(
        lock_path,
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o600,
    )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _publish_exclusive(source: Path, destination: Path) -> None:
    """Atomically publish a directory without replacing an existing path."""
    libc = ctypes.CDLL(None, use_errno=True)

    if sys.platform.startswith("linux"):
        try:
            rename = libc.renameat2
        except AttributeError as exc:
            raise StaticBuildError("Exclusive directory publication is unavailable") from exc

        rename.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int

        # Linux: AT_FDCWD=-100, RENAME_NOREPLACE=1.
        result = rename(
            -100,
            os.fsencode(source),
            -100,
            os.fsencode(destination),
            1,
        )
    elif sys.platform == "darwin":
        try:
            rename = libc.renamex_np
        except AttributeError as exc:
            raise StaticBuildError("Exclusive directory publication is unavailable") from exc

        rename.argtypes = (
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int

        # macOS: RENAME_EXCL=0x4.
        result = rename(
            os.fsencode(source),
            os.fsencode(destination),
            0x4,
        )
    else:
        raise StaticBuildError("Exclusive directory publication is unsupported on this platform")

    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(
            error_number,
            os.strerror(error_number),
            str(destination),
        )


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _clean_stale_temporaries(root: Path) -> None:
    """Remove old, real temporary directories under the publication lock."""
    cutoff = time.time() - STALE_TEMP_SECONDS

    with os.scandir(root) as entries:
        for entry in entries:
            if not entry.name.startswith(".tmp-"):
                continue

            try:
                info = entry.stat(follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode) or info.st_mtime >= cutoff:
                    continue

                # shutil.rmtree rejects symlink roots and uses fd-based
                # traversal on supported platforms.
                shutil.rmtree(root / entry.name)
            except FileNotFoundError:
                continue


def create_static_snapshot(source: Path, root: Path) -> StaticBuild:
    """Publish a verified static tree without overwriting existing builds."""
    source = source.absolute()
    root = root.absolute()

    _reject_symlink_components(root)

    root.mkdir(parents=True, exist_ok=True, mode=0o750)

    _reject_symlink_components(root)

    with _publication_lock(root):
        _clean_stale_temporaries(root)
        for _attempt in range(3):
            before = _inventory(source)
            manifest = _manifest_bytes(before)
            build_id = _manifest_id(manifest)
            destination = root / build_id

            if destination.exists() or destination.is_symlink():
                if verify_static_snapshot(destination, build_id):
                    return StaticBuild(build_id, destination)
                raise StaticBuildError(
                    f"Existing static snapshot {build_id} failed integrity verification "
                    f"at {destination}; manual recovery required"
                )

            temporary = Path(tempfile.mkdtemp(prefix=".tmp-", dir=root))

            try:
                os.chmod(temporary, 0o700)

                for relative, expected_hash in before.items():
                    origin = source / relative
                    target = temporary / relative
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o750)

                    data = origin.read_bytes()
                    if hashlib.sha256(data).hexdigest() != expected_hash:
                        break

                    with target.open("xb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())

                    os.chmod(target, 0o640)
                else:
                    after = _inventory(source)

                    if after != before:
                        continue

                    manifest_path = temporary / MANIFEST_NAME
                    with manifest_path.open("xb") as stream:
                        stream.write(manifest)
                        stream.flush()
                        os.fsync(stream.fileno())

                    os.chmod(manifest_path, 0o640)

                    for directory, _subdirs, _names in os.walk(temporary, topdown=False):
                        os.chmod(directory, 0o700)
                        _sync_directory(Path(directory))

                    if not verify_static_snapshot(temporary, build_id):
                        raise StaticBuildError("Prepared snapshot failed verification")

                    if destination.exists() or destination.is_symlink():
                        raise StaticBuildError("Snapshot destination appeared during publication")

                    _publish_exclusive(temporary, destination)
                    _sync_directory(root)
                    return StaticBuild(build_id, destination)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)

        raise StaticBuildError("Static source changed during snapshot creation")
