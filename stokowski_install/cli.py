"""CLI for `stokowski-install-service`.

Subcommands: install, uninstall, status, logs.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import platform as _platform
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from stokowski import __version__

from . import paths, render

console = Console()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stokowski-install-service",
        description=(
            "Register Stokowski as a launchd LaunchAgent (macOS) or "
            "systemd user service (Linux)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_install = sub.add_parser("install", help="Install and start the service")
    p_install.add_argument(
        "--workflow", type=Path, default=None,
        help="Path to workflow.yaml (default: auto-detect from cwd)",
    )
    p_install.add_argument(
        "--label", default=paths.DEFAULT_LABEL,
        help=f"Service label (default: {paths.DEFAULT_LABEL})",
    )
    p_install.add_argument(
        "--system", action="store_true",
        help="Install system-wide (requires sudo)",
    )
    p_install.add_argument(
        "--no-sudo", action="store_true",
        help="Don't re-exec via sudo for --system installs",
    )
    p_install.add_argument(
        "--force", action="store_true",
        help="Overwrite an existing unit file",
    )

    p_uninstall = sub.add_parser("uninstall", help="Stop and remove the service")
    p_uninstall.add_argument(
        "--label", default=paths.DEFAULT_LABEL,
    )
    p_uninstall.add_argument(
        "--system", action="store_true",
        help="Uninstall the system-level service",
    )
    p_uninstall.add_argument(
        "--no-sudo", action="store_true",
    )

    p_status = sub.add_parser("status", help="Show service status")
    p_status.add_argument(
        "--label", default=paths.DEFAULT_LABEL,
    )

    p_logs = sub.add_parser("logs", help="Show service logs")
    p_logs.add_argument("-f", "--follow", action="store_true")
    p_logs.add_argument("--lines", type=int, default=50)
    p_logs.add_argument(
        "--label", default=paths.DEFAULT_LABEL,
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "install":
            return _install(args)
        if args.command == "uninstall":
            return _uninstall(args)
        if args.command == "status":
            return _status(args)
        if args.command == "logs":
            return _logs(args)
    except _UserError as e:
        console.print(f"[red]error:[/red] {e}")
        return 2
    return 0


class _UserError(Exception):
    pass


def _detect_platform() -> str:
    name = _platform.system().lower()
    if name == "darwin":
        return "darwin"
    if name == "linux":
        return "linux"
    raise _UserError(
        f"unsupported platform: {_platform.system()!r} "
        "(supported: darwin, linux)"
    )


def _template_path(plat: str) -> Path:
    here = Path(__file__).resolve().parent
    fname = "stokowski.plist" if plat == "darwin" else "stokowski.service"
    candidate = here / "templates" / fname
    if not candidate.is_file():
        raise _UserError(f"template not found: {candidate}")
    return candidate


def _wrapper_template_path(plat: str) -> Path | None:
    if plat != "darwin":
        return None
    here = Path(__file__).resolve().parent
    candidate = here / "templates" / "stokowski-daemon.sh"
    if not candidate.is_file():
        raise _UserError(f"template not found: {candidate}")
    return candidate


def _write_wrapper(plat: str, python: Path, workflow: Path) -> Path:
    """Render and install the launchd wrapper script (macOS only).

    The wrapper sources the user's login profile so the daemon inherits the
    same PATH (npm, nvm, pnpm, fnm, etc.) as an interactive shell. Returns
    the wrapper path.
    """
    tpl_path = _wrapper_template_path(plat)
    assert tpl_path is not None
    tpl = render.load_template(tpl_path)
    subs = {
        "PYTHON": str(python),
        "WORKFLOW": str(workflow),
    }
    rendered = render.render_template(tpl, subs)
    out = paths.wrapper_path()
    out.write_text(rendered, encoding="utf-8")
    out.chmod(0o755)
    return out


def _resolve_workflow(args: argparse.Namespace) -> Path:
    if args.workflow is not None:
        p = args.workflow.expanduser().resolve()
        if not p.is_file():
            raise _UserError(f"workflow file not found: {p}")
        return p
    detected = paths.resolve_default_workflow(Path.cwd())
    if detected is None:
        raise _UserError(
            f"no workflow file found in {Path.cwd()} — pass --workflow PATH "
            "or cd to a directory containing workflow.yaml"
        )
    return detected


def _build_substitutions(workflow: Path, label: str, wrapper: Path | None) -> dict[str, str]:
    workdir = workflow.parent.resolve()
    logdir = paths.resolve_logdir()
    python = paths.resolve_venv_python()
    # Build the daemon's PATH: venv bin first, then the user's ~/.local/bin
    # (where the `claude` CLI lives), then whatever PATH the install-time
    # shell has so npm/nvm/pnpm/fnm shims resolve.
    venv_bin = str(python.parent)
    local_bin = str(Path.home() / ".local" / "bin")
    system_path = os.environ.get("PATH", "")
    seen: set[str] = set()
    path_parts: list[str] = []
    for part in [venv_bin, local_bin, *system_path.split(":")]:
        if part and part not in seen:
            seen.add(part)
            path_parts.append(part)
    path_value = ":".join(path_parts)
    subs = {
        "LABEL": label,
        "PYTHON": str(python),
        "WORKFLOW": str(workflow),
        "WORKDIR": str(workdir),
        "LOGDIR": str(logdir),
        "PATH": path_value,
    }
    if wrapper is not None:
        subs["WRAPPER"] = str(wrapper)
    return subs


def _reexec_with_sudo(args: argparse.Namespace) -> int:
    """Re-execute the current command with sudo, transferring control."""
    sudo_args = ["sudo", sys.executable, "-m", "stokowski_install", *sys.argv[1:]]
    console.print(f"[yellow]re-executing with sudo:[/yellow] {' '.join(sudo_args)}")
    try:
        os.execvp("sudo", sudo_args)
    except FileNotFoundError:
        raise _UserError("sudo not found on this system")
    return 0  # unreachable


def _print_summary(
    label: str, workflow: Path, logdir: Path, python: Path,
    unit_path: Path, plat: str,
) -> None:
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Stokowski", __version__)
    t.add_row("Platform", plat)
    t.add_row("Label", label)
    t.add_row("Unit file", str(unit_path))
    t.add_row("Working dir", str(workflow.parent.resolve()))
    t.add_row("Workflow", str(workflow))
    t.add_row("Python", str(python))
    t.add_row(
        "Logs",
        f"{logdir}/stokowski.out.log  +  {logdir}/stokowski.err.log",
    )
    if plat == "darwin":
        t.add_row(
            "Manage",
            f"launchctl list | grep {label}    "
            f"launchctl print gui/{os.getuid()}/{label}",
        )
    else:
        t.add_row(
            "Manage",
            f"systemctl --user status {label}    "
            f"journalctl --user -u {label} -f",
        )
    console.print(Panel(
        t,
        title="[bold green]Service installed[/bold green]",
        border_style="green",
    ))


def _install(args: argparse.Namespace) -> int:
    if args.system and not args.no_sudo and os.geteuid() != 0:
        return _reexec_with_sudo(args)

    plat = _detect_platform()
    workflow = _resolve_workflow(args)
    label = args.label
    logdir = paths.resolve_logdir()
    python = paths.resolve_venv_python()

    wrapper: Path | None = None
    if plat == "darwin":
        wrapper = _write_wrapper(plat, python, workflow)
        console.print(f"[green]wrote[/green] {wrapper}")

    tpl = render.load_template(_template_path(plat))
    subs = _build_substitutions(workflow, label, wrapper)
    rendered = render.render_template(tpl, subs)

    unit_path = paths.unit_path(plat, label, system=args.system)
    if unit_path.exists() and not args.force:
        raise _UserError(
            f"unit file already exists: {unit_path}  (pass --force to overwrite)"
        )

    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(rendered, encoding="utf-8")
    console.print(f"[green]wrote[/green] {unit_path}")

    if plat == "darwin":
        from . import platform_macos
        asyncio.run(platform_macos.install(unit_path, label))
    else:
        from . import platform_linux
        asyncio.run(platform_linux.install(unit_path, label))

    _print_summary(label, workflow, logdir, python, unit_path, plat)
    return 0


def _uninstall(args: argparse.Namespace) -> int:
    if args.system and not args.no_sudo and os.geteuid() != 0:
        return _reexec_with_sudo(args)

    plat = _detect_platform()
    label = args.label
    unit_path = paths.unit_path(plat, label, system=args.system)

    if plat == "darwin":
        from . import platform_macos
        asyncio.run(platform_macos.uninstall(label, unit_path))
    else:
        from . import platform_linux
        asyncio.run(platform_linux.uninstall(label, unit_path))

    if plat == "darwin":
        wp = paths.wrapper_path()
        if wp.exists():
            wp.unlink()
            console.print(f"[green]removed[/green] {wp}")

    console.print(f"[green]uninstalled[/green] {label}")
    return 0


def _status(args: argparse.Namespace) -> int:
    plat = _detect_platform()
    label = args.label
    unit_path = paths.unit_path(plat, label, system=False)
    sys_unit = paths.unit_path(plat, label, system=True)
    location = "system" if sys_unit.exists() and not unit_path.exists() else "user"
    real_unit = sys_unit if location == "system" else unit_path

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column()
    t.add_row("Platform", plat)
    t.add_row("Label", label)
    t.add_row("Scope", location)
    t.add_row("Unit file", str(real_unit))
    t.add_row("Exists", "yes" if real_unit.exists() else "no")
    console.print(t)

    if not real_unit.exists():
        return 0

    if plat == "darwin":
        from . import platform_macos
        result = asyncio.run(platform_macos.status(label))
    else:
        from . import platform_linux
        result = asyncio.run(platform_linux.status(label))
    console.print(Panel(result or "(no output)", title="[bold]status[/bold]"))
    return 0


def _logs(args: argparse.Namespace) -> int:
    plat = _detect_platform()
    label = args.label
    logdir = paths.resolve_logdir()
    if plat == "darwin":
        from . import platform_macos
        return asyncio.run(
            platform_macos.logs(logdir, args.lines, args.follow)
        )
    from . import platform_linux
    return asyncio.run(platform_linux.logs(label, args.lines, args.follow))


if __name__ == "__main__":
    raise SystemExit(main())
