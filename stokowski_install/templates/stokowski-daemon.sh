#!/bin/sh
# Launchd wrapper for `stokowski`. Rebuilds a login-shell-like PATH so
# subprocesses (the `claude` CLI shim, gh, brew, etc.) see the same
# toolchain an interactive terminal would. The plist's PATH is just the
# install-time snapshot — often missing Homebrew's /opt/homebrew/bin or
# /usr/local/bin because launchd does not source ~/.zprofile.

set -eu

PYTHON_BIN="__PYTHON__"
WORKFLOW="__WORKFLOW__"

# Pull in the system-managed PATH entries from /etc/paths and
# /etc/paths.d/*. `path_helper -s` prints a `PATH="..."` line for sh-style
# shells. Falls back silently if the helper is missing (non-Apple shim).
if [ -x /usr/libexec/path_helper ]; then
    PATH_VALUE=$(/usr/libexec/path_helper -s 2>/dev/null | sed -n 's/^PATH="\(.*\)"$/\1/p')
    if [ -n "$PATH_VALUE" ]; then
        export PATH="$PATH_VALUE"
    fi
fi

# Prepend the user-local bin (where the `claude` CLI lives) and the
# Homebrew-controlled directories that Homebrew's shellenv would add
# on a login shell. Idempotent: missing dirs in the export are harmless.
for _dir in \
    "$HOME/.local/bin" \
    /opt/homebrew/bin \
    /opt/homebrew/sbin \
    /usr/local/bin \
    /usr/local/sbin \
    /Library/Apple/usr/bin
do
    case ":$PATH:" in
        *":${_dir}:"*) ;;       # already present
        *) PATH="${_dir}:$PATH" ;;
    esac
done
unset _dir
export PATH

export PYTHONUNBUFFERED=1

# launchd does not provide $PWD by default, but subprocesses like the
# `claude` CLI shim (which sources nvm.sh under `set -u`) reference it
# unconditionally and abort with "PWD: unbound variable" when missing.
WORKFLOW_DIR=$(cd "$(dirname "$WORKFLOW")" && pwd)
cd "$WORKFLOW_DIR"
export PWD="$WORKFLOW_DIR"

exec "$PYTHON_BIN" -m stokowski "$WORKFLOW" "$@"
