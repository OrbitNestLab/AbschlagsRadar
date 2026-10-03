"""Install one complete bridge revision with rollback; never touch HA user data."""

import hashlib
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

DOMAIN = "abschlagsradar"


def mark_restart(data_root):
    """A writable App-data directory must not redirect a privileged startup write."""
    marker = data_root / "bridge-restart-needed"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    descriptor = os.open(marker, flags, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write("restart needed\n")


def release_files(root):
    """Reject links before copying and ignore generated Python caches."""
    if root.is_symlink():
        raise ValueError("Refusing linked integration directory")
    files = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Refusing linked integration file")
        if path.is_file() and "__pycache__" not in path.parts:
            files[path.relative_to(root)] = path
    return files


def check_manifest(root):
    if json.loads((root / "manifest.json").read_text()).get("domain") != DOMAIN:
        raise ValueError("Refusing unrelated integration")


def ensure_bridge(source, config_root, data_root):
    source, config_root, data_root = Path(source), Path(config_root), Path(data_root)
    if any(
        path.is_symlink() for path in (data_root, data_root / "bridge-backups", data_root / "bridge-restart-needed")
    ):
        raise ValueError("Refusing linked App data")
    marker = data_root / "bridge-restart-needed"
    if marker.exists() and not marker.is_file():
        raise ValueError("Refusing non-file restart marker")
    if not config_root.is_dir() or not (config_root / "configuration.yaml").is_file():
        raise ValueError("Home Assistant configuration mount is missing")
    parent = config_root / "custom_components"
    target = parent / DOMAIN
    old = parent / ".abschlagsradar-previous"
    if parent.is_symlink() or target.is_symlink() or old.is_symlink():
        raise ValueError("Refusing linked integration directory")
    check_manifest(source)
    files = release_files(source)
    parent.mkdir(exist_ok=True)
    # Recover a process interruption between the two same-filesystem renames.
    if old.exists():
        check_manifest(old)
        release_files(old)
        if not target.exists():
            old.replace(target)
        else:
            check_manifest(target)
            release_files(target)
            mark_restart(data_root)
            shutil.rmtree(old)
    if target.exists():
        check_manifest(target)
        installed = release_files(target)
        if set(installed) == set(files) and all(
            hashlib.sha256(src.read_bytes()).digest() == hashlib.sha256(installed[name].read_bytes()).digest()
            for name, src in files.items()
        ):
            return False
    backups = data_root / "bridge-backups"
    if target.exists():
        backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        shutil.copytree(target, backups / stamp, ignore=shutil.ignore_patterns("__pycache__"))
    stage = Path(tempfile.mkdtemp(prefix=".abschlagsradar-stage-", dir=parent))
    stage.chmod(0o755)
    try:
        for name, src in files.items():
            dst = stage / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            dst.chmod(0o644)
        if target.exists():
            target.replace(old)
        try:
            stage.replace(target)
        except Exception:
            if old.exists():
                old.replace(target)
            raise
        # Record this before cleanup so a cleanup error cannot skip the restart.
        mark_restart(data_root)
        if old.exists():
            shutil.rmtree(old)
        if backups.exists():
            for previous in sorted(backups.iterdir())[:-3]:
                shutil.rmtree(previous)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return True
