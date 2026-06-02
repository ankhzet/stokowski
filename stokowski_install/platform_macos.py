"""macOS launchd install / uninstall / status / logs."""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Result:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def _domain() -> str:
    return f"gui/{os.getuid()}"


async def _run(cmd: list[str], check: bool = True) -> Result:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()
    out = Result(
        args=cmd,
        returncode=proc.returncode or 0,
        stdout=stdout_b.decode("utf-8", errors="replace"),
        stderr=stderr_b.decode("utf-8", errors="replace"),
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, out.stdout, out.stderr,
        )
    return out


async def install(unit_path: Path, label: str) -> None:
    """Validate the plist, bootout any prior copy, bootstrap the new one."""
    # plutil -lint fails fast on syntax errors.
    await _run(["plutil", "-lint", str(unit_path)], check=True)
    await _bootout_if_loaded(label)
    await _run(["launchctl", "bootstrap", _domain(), str(unit_path)], check=True)
    await _run(["launchctl", "enable", f"{_domain()}/{label}"], check=True)
    await _run(["launchctl", "kickstart", f"{_domain()}/{label}"], check=False)


async def uninstall(label: str, unit_path: Path) -> None:
    await _bootout_if_loaded(label)
    if unit_path.exists():
        unit_path.unlink()


async def _bootout_if_loaded(label: str) -> None:
    """Bootout a service if it's loaded; ignore 'not loaded' errors."""
    target = f"{_domain()}/{label}"
    await _run(["launchctl", "bootout", target], check=False)


async def status(label: str) -> str:
    target = f"{_domain()}/{label}"
    proc = await _run(["launchctl", "print", target], check=False)
    if proc.returncode != 0:
        return f"not loaded (rc={proc.returncode}): {proc.stderr.strip()}"
    # Print only the first few useful lines.
    head = "\n".join(proc.stdout.splitlines()[:8])
    return head


async def logs(log_dir: Path, lines: int, follow: bool) -> int:
    out_log = log_dir / "stokowski.out.log"
    err_log = log_dir / "stokowski.err.log"
    if not out_log.exists() and not err_log.exists():
        print(f"(no log files yet under {log_dir})")
        return 0
    files = [p for p in (err_log, out_log) if p.exists()]
    if follow:
        # Stream tail directly to the parent's stdout; don't capture.
        proc = await asyncio.create_subprocess_exec(
            "tail", "-F", *[str(p) for p in files],
            stdout=None, stderr=None,
        )
        return await proc.wait()
    for path in files:
        print(f"--- {path} ---")
        # Read the tail of the file directly — _run captures stdout to
        # PIPE and discards it, so shelling out to `tail` would lose
        # the lines.
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"(error reading {path}: {e})")
            continue
        tail_lines = content.splitlines()[-lines:]
        for line in tail_lines:
            print(line)
    return 0
