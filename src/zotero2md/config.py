"""Central configuration — paths are configurable via environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a ``.env`` file in the current working directory
# (or any parent directory), if present. Existing environment variables
# always take precedence over the ones defined in the .env file.
load_dotenv()


def _env_path(var: str, default: str) -> Path:
    """Read a path from an environment variable or fall back to *default*."""
    return Path(os.environ.get(var, default)).expanduser()



# ── Paths ──────────────────────────────────────────────────────────────

ZOTERO_DIR: Path = _env_path("ZOTERO_DIR", str(Path.home() / "Zotero"))

OUTPUT_FOLDER: Path = _env_path("OUTPUT_FOLDER", str(Path.home() / "Obsidian" / "Paper"))

DB_MAIN: Path = ZOTERO_DIR / "zotero.sqlite"

# Sync-state file (stores last-sync timestamp)
SYNC_STATE_FILE: Path = OUTPUT_FOLDER / ".zotero_sync_state.json"