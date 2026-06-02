"""Template substitution for service unit files.

The templates use ``__PLACEHOLDER__`` syntax. A missing placeholder in the
substitution dict is an error — the renderer refuses to produce a partially
rendered unit that launchd/systemd would then refuse to load.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"__([A-Z][A-Z0-9_]*)__")


def render_template(template: str, substitutions: dict[str, str]) -> str:
    """Replace ``__KEY__`` placeholders in *template* using *substitutions*."""

    def _replace(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in substitutions:
            raise ValueError(f"unreplaced placeholder: __{name}__")
        return substitutions[name]

    return _PLACEHOLDER_RE.sub(_replace, template)


def list_placeholders(template: str) -> list[str]:
    """Return the placeholders used in *template*, in order of first appearance."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _PLACEHOLDER_RE.finditer(template):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")
