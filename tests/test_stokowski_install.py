"""Tests for stokowski_install (no real launchd/systemd required)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from stokowski_install import paths, render


# ── paths.resolve_venv_python ────────────────────────────────────────────────


def test_resolve_venv_python_honors_virtual_env(tmp_path, monkeypatch):
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    fake_python = venv / "bin" / "python"
    fake_python.write_text("")
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))
    monkeypatch.chdir(tmp_path)
    assert paths.resolve_venv_python() == fake_python


def test_resolve_venv_python_finds_local_dotvenv(tmp_path, monkeypatch):
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    fake_python = tmp_path / ".venv" / "bin" / "python"
    fake_python.write_text("")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.chdir(tmp_path)
    assert paths.resolve_venv_python() == fake_python


def test_resolve_venv_python_walks_up_to_find_venv(tmp_path, monkeypatch):
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    fake_python = tmp_path / ".venv" / "bin" / "python"
    fake_python.write_text("")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)
    assert paths.resolve_venv_python() == fake_python


def test_resolve_venv_python_falls_back_to_sys_executable(tmp_path, monkeypatch):
    import sys
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.chdir(tmp_path)
    assert paths.resolve_venv_python() == Path(sys.executable)


# ── paths.resolve_logdir ────────────────────────────────────────────────────


def test_resolve_logdir_creates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    out = paths.resolve_logdir()
    assert out == tmp_path / "stokowski" / "logs"
    assert out.is_dir()


def test_resolve_logdir_honors_xdg_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    out = paths.resolve_logdir()
    assert out == tmp_path / "xdg" / "stokowski" / "logs"
    assert out.is_dir()


# ── paths.resolve_default_workflow ───────────────────────────────────────────


def test_resolve_default_workflow_finds_yaml(tmp_path):
    (tmp_path / "workflow.yaml").write_text("tracker: {}\n")
    assert paths.resolve_default_workflow(tmp_path) == tmp_path / "workflow.yaml"


def test_resolve_default_workflow_prefers_yaml_over_md(tmp_path):
    (tmp_path / "workflow.yaml").write_text("")
    (tmp_path / "WORKFLOW.md").write_text("")
    assert paths.resolve_default_workflow(tmp_path) == tmp_path / "workflow.yaml"


def test_resolve_default_workflow_returns_none_when_missing(tmp_path):
    assert paths.resolve_default_workflow(tmp_path) is None


# ── paths.unit_path ─────────────────────────────────────────────────────────


def test_unit_path_darwin_user():
    p = paths.unit_path("darwin", "com.example.foo")
    assert p == Path.home() / "Library" / "LaunchAgents" / "com.example.foo.plist"


def test_unit_path_darwin_system():
    p = paths.unit_path("darwin", "com.example.foo", system=True)
    assert p == Path("/Library/LaunchDaemons") / "com.example.foo.plist"


def test_unit_path_linux_user():
    p = paths.unit_path("linux", "stokowski")
    assert p == Path.home() / ".config" / "systemd" / "user" / "stokowski.service"


def test_unit_path_linux_system():
    p = paths.unit_path("linux", "stokowski", system=True)
    assert p == Path("/etc/systemd/system") / "stokowski.service"


def test_unit_path_unsupported_platform_raises():
    with pytest.raises(ValueError):
        paths.unit_path("windows", "stokowski")


# ── render.render_template ──────────────────────────────────────────────────


def test_render_template_substitutes_known_keys():
    out = render.render_template(
        "label=__LABEL__ python=__PYTHON__",
        {"LABEL": "local.x", "PYTHON": "/usr/bin/python"},
    )
    assert out == "label=local.x python=/usr/bin/python"


def test_render_template_raises_on_missing_placeholder():
    with pytest.raises(ValueError, match="__FOO__"):
        render.render_template("hello __FOO__", {})


def test_render_template_leaves_unknown_passes_through():
    # Anything not matching __[A-Z][A-Z0-9_]*__ is untouched.
    out = render.render_template("a__b__c __FOO__ d", {"FOO": "x"})
    assert out == "a__b__c x d"


def test_render_template_idempotent_for_already_rendered_text():
    # A value that contains __BAR__ should be safe to re-render.
    out = render.render_template(
        "__A__", {"A": "__B__", "B": "nope"},
    )
    assert out == "__B__"


def test_list_placeholders_returns_in_order():
    tpl = "__FOO__ __BAR__ __FOO__ __BAZ__"
    assert render.list_placeholders(tpl) == ["FOO", "BAR", "BAZ"]


def test_load_template_reads_file(tmp_path):
    f = tmp_path / "tpl.txt"
    f.write_text("__X__-__Y__")
    assert render.load_template(f) == "__X__-__Y__"


# ── cli._default_system_bin_paths ───────────────────────────────────────────


def test_default_system_bin_paths_darwin():
    from stokowski_install.cli import _default_system_bin_paths
    parts = _default_system_bin_paths("darwin")
    assert "/opt/homebrew/bin" in parts
    assert "/opt/homebrew/sbin" in parts
    assert "/usr/local/bin" in parts
    assert "/usr/local/sbin" in parts
    assert "/Library/Apple/usr/bin" in parts


def test_default_system_bin_paths_linux():
    from stokowski_install.cli import _default_system_bin_paths
    parts = _default_system_bin_paths("linux")
    assert "/usr/local/sbin" in parts
    assert "/usr/local/bin" in parts
    # Linux must not inherit the macOS Homebrew paths.
    assert "/opt/homebrew/bin" not in parts
    assert "/Library/Apple/usr/bin" not in parts


def test_default_system_bin_paths_unknown_empty():
    from stokowski_install.cli import _default_system_bin_paths
    assert _default_system_bin_paths("plan9") == []
