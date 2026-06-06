#!/bin/sh
# Launchd wrapper for `stokowski`. Prepends the user's local bin
# (where the `claude` CLI is installed) and execs the daemon via the
# venv's Python interpreter. PATH is taken from the plist's
# EnvironmentVariables, which the installer populates with the user's
# captured PATH plus ~/.local/bin.

set -eu

PYTHON_BIN="__PYTHON__"
WORKFLOW="__WORKFLOW__"

export PATH="$HOME/.local/bin:$PATH"
export PYTHONUNBUFFERED=1

# launchd does not provide $PWD by default, but subprocesses like the
# `claude` CLI shim (which sources nvm.sh under `set -u`) reference it
# unconditionally and abort with "PWD: unbound variable" when missing.
WORKFLOW_DIR=$(cd "$(dirname "$WORKFLOW")" && pwd)
cd "$WORKFLOW_DIR"
export PWD="$WORKFLOW_DIR"

exec "$PYTHON_BIN" -m stokowski "$WORKFLOW" "$@"
