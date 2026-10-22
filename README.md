# Zotero → Obsidian Sync

Incremental sync tool that exports annotated papers from a local [Zotero](https://www.zotero.org/) database to [Obsidian](https://obsidian.md/)-compatible Markdown files.

Each paper is rendered as a standalone `.md` file with YAML frontmatter, Zotero deep-links, abstract, highlights/annotations, and Zotero notes.

## Features

- **Incremental sync** — only items modified since the last run are re-exported
- **Deletion handling** — Markdown files for deleted Zotero items are removed
- **Rich annotations** — highlights, comments, and annotation tags are preserved
- **Zotero deep-links** — every annotation links back to the exact PDF page in Zotero
- **YAML frontmatter** — title, citation key, authors, date, and tags for Obsidian/Dataview

## Requirements

- Python ≥ 3.12
- A local Zotero database (`zotero.sqlite`) — the [Zotero desktop app](https://www.zotero.org/download/) must be installed and have been run at least once
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- (Recommended) the Zotero plugin [Better BibTeX](https://retorque.re/zotero-better-bibtex/) so that items have a `citationKey` — otherwise the Zotero item key is used as filename/citation key fallback

> ⚠️ **Important:** Zotero locks `zotero.sqlite` exclusively while running. This tool copies the database file to a temporary location before reading it, so you can run a sync while Zotero is open. However, changes made in Zotero **after** the sync has started copying the file won't be visible until the next run.

## Installation

### Option A — with `uv` (recommended)

```bash
# Clone the repository
git clone https://github.com/qucoso/zotero2md.git
cd zotero2md

# Create virtual environment and install dependencies
uv sync

# Install the CLI tool into the virtual environment
uv pip install -e .
```

### Option B — with `pip`

```bash
git clone https://github.com/qucoso/zotero2md.git
cd zotero2md

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .
```

## Configuration

The tool reads its configuration from environment variables. The easiest way to set these is via a `.env` file in the project root — it is loaded automatically at startup.

1. Copy the example file:

   ```bash
   cp .env.example .env
   ```

2. Open `.env` and adjust the two paths to your system:

   ```dotenv
   # Path to your Zotero data directory (the folder that contains zotero.sqlite)
   ZOTERO_DIR=/home/user/Zotero

   # Output folder where the Markdown files should be written to
   # (usually a folder/vault inside your Obsidian vault)
   OUTPUT_FOLDER=/home/user/Obsidian/Paper
   ```

   | Variable         | Description                                                                 | Default                    |
   |------------------|-------------------------------------------------------------------------------|-----------------------------|
   | `ZOTERO_DIR`     | Path to the folder containing `zotero.sqlite` (Zotero's data directory)       | `~/Zotero`                  |
   | `OUTPUT_FOLDER`  | Destination folder for the generated Markdown files (e.g. your Obsidian vault)| `~/Obsidian/Paper`          |

   You can find your Zotero data directory in Zotero under **Edit → Settings → Advanced → Files and Folders → Data Directory Location**.

3. Alternatively, you can export the variables directly in your shell instead of using a `.env` file:

   ```bash
   export ZOTERO_DIR="/home/user/Zotero"
   export OUTPUT_FOLDER="/home/user/Obsidian/Paper"
   ```

   Environment variables always take precedence over values defined in `.env`.

The tool automatically creates the `OUTPUT_FOLDER` (including parent directories) if it doesn't exist yet, and stores its sync state in a hidden file `.zotero_sync_state.json` inside that folder.

## Usage

Once installed and configured, start a sync run with:

```bash
zotero2md
```

This is equivalent to:

```bash
python -m zotero2md
```

or, if you didn't install the package as a CLI tool:

```bash
uv run zotero2md
```

The first run performs a **full sync** of all items in your Zotero library. Subsequent runs are **incremental** — only items (and their notes/annotations) changed since the last sync are re-exported, and Markdown files for items deleted in Zotero are removed automatically.

### Automating the sync (optional)

To keep your Obsidian vault continuously up to date, you can schedule the command to run periodically, e.g. via `cron`:

```bash
# Run every 30 minutes
*/30 * * * * cd /path/to/zotero2md && /path/to/.venv/bin/zotero2md >> /tmp/zotero2md.log 2>&1
```

## Troubleshooting

- **`FileNotFoundError: Zotero DB nicht gefunden unter ...`**
  Your `ZOTERO_DIR` is incorrect, or Zotero has never been started (so `zotero.sqlite` doesn't exist yet). Check the path in Zotero under **Edit → Settings → Advanced → Files and Folders**.

- **No citation key / files named after Zotero keys instead of readable names**
  Install and enable the [Better BibTeX](https://retorque.re/zotero-better-bibtex/) plugin in Zotero, which automatically generates a `citationKey` for every item.

- **Changes in Zotero not reflected after sync**
  Make sure Zotero has saved the changes to disk (Zotero commits changes to SQLite fairly quickly, but there can be a short delay). Also check that `.zotero_sync_state.json` in your `OUTPUT_FOLDER` wasn't manually altered or deleted, as that would trigger a full re-sync.

- **Permission errors writing to `OUTPUT_FOLDER`**
  Make sure the folder is writable by your user and not currently opened/locked by another application (e.g. a cloud sync client).

## License

MIT
