"""Enable `python -m stokowski_install` (used by the sudo re-exec path)."""

from stokowski_install.cli import main

raise SystemExit(main())
