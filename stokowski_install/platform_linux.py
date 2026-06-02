"""Linux systemd (user) install / uninstall / status / logs."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Result:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


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
    """Reload the user daemon, enable + start the service."""
    await _run(["systemctl", "--user", "daemon-reload"], check=True)
    await _run(
        ["systemctl", "--user", "enable", "--now", f"{label}.service"],
        check=True,
    )


async def uninstall(label: str, unit_path: Path) -> None:
    """Disable + stop the service (idempotent) and remove the unit file."""
    await _run(
        ["systemctl", "--user", "disable", "--now", f"{label}.service"],
        check=False,
    )
    if unit_path.exists():
        unit_path.unlink()
    await _run(["systemctl", "--user", "daemon-reload"], check=False)
    await _run(["systemctl", "--user", "reset-failed", label], check=False)


async def status(label: str) -> str:
    state_proc = await _run(
        ["systemctl", "--user", "is-active", f"{label}.service"],
        check=False,
    )
    pid_proc = await _run(
        [
            "systemctl", "--user", "show", f"{label}.service",
            "--property=MainPID", "--value",
        ],
        check=False,
    )
    state = state_proc.stdout.strip() or f"unknown (rc={state_proc.returncode})"
    pid = pid_proc.stdout.strip() if pid_proc.returncode == 0 else "?"
    return f"state={state}  pid={pid}"


async def logs(label: str, lines: int, follow: bool) -> int:
    cmd = ["journalctl", "--user", "-u", f"{label}.service", "-n", str(lines)]
    if follow:
        cmd.append("-f")
    return (await _run(cmd, check=False)).returncode
