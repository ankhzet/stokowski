"""Path resolution for the installer.

Mirrors the workflow auto-detect logic in `stokowski/main.py:cli()` so that
running `stokowski-install-service install` from a directory containing
`workflow.yaml` Just Works.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_LABEL = "local.stokowski.daemon"
WRAPPER_NAME = "stokowski-daemon"


def resolve_wrapper_dir() -> Path:
    """Per-user directory for the daemon launch wrapper, creating it."""
    wrapper_dir = Path.home() / ".local" / "share" / "stokowski" / "bin"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    return wrapper_dir


def wrapper_path() -> Path:
    """Path of the daemon launch wrapper script."""
    return resolve_wrapper_dir() / WRAPPER_NAME


def resolve_venv_python() -> Path:
    """Pick the Python interpreter that will run the daemon.

    Priority:
    1. ``$VIRTUAL_ENV`` env var (set when a venv is activated).
    2. A ``.venv`` adjacent to or above the current working directory.
    3. The interpreter running this installer.
    """
    venv = os.environ.get("VIRTUAL_ENV", "").strip()
    if venv:
        candidate = _interpreter_in_venv(Path(venv))
        if candidate is not None:
            return candidate

    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidate = _interpreter_in_venv(parent / ".venv")
        if candidate is not None:
            return candidate

    return Path(sys.executable)


def _interpreter_in_venv(venv_dir: Path) -> Path | None:
    """Return the Python binary inside a venv, or None if not a venv."""
    if not venv_dir.is_dir():
        return None
    # Unix layout (.venv/bin/python) is what we install on macOS / Linux.
    unix = venv_dir / "bin" / "python"
    if unix.is_file():
        return unix
    return None


def resolve_logdir() -> Path:
    """Return the per-user log directory for Stokowski, creating it.
    Honors ``$XDG_DATA_HOME`` (defaults to ``~/.local/share`` on Linux).
    """
    base = os.environ.get("XDG_DATA_HOME", "").strip()
    if base:
        root = Path(base)
    else:
        root = Path.home() / ".local" / "share"
    logdir = root / "stokowski" / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    return logdir


def resolve_default_workflow(cwd: Path) -> Path | None:
    """Mirror the auto-detect logic in stokowski/main.py:cli()."""
    for name in ("workflow.yaml", "workflow.yml", "WORKFLOW.md"):
        candidate = cwd / name
        if candidate.is_file():
            return candidate
    return None


def unit_path(platform: str, label: str, *, system: bool = False) -> Path:
    """On-disk path of the service unit file."""
    if platform == "darwin":
        if system:
            return Path("/Library/LaunchDaemons") / f"{label}.plist"
        return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    if platform == "linux":
        if system:
            return Path("/etc/systemd/system") / f"{label}.service"
        return Path.home() / ".config" / "systemd" / "user" / f"{label}.service"
    raise ValueError(f"unsupported platform: {platform!r}")
