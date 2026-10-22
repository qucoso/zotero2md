"""High-level sync orchestration."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.progress import track

from .config import OUTPUT_FOLDER
from .database import (
    connect,
    get_changed_item_ids,
    get_deleted_item_keys,
    get_items,
    load_sync_state,
    save_sync_state,
)

from .renderer import render_item_markdown

console = Console()


def _safe_filename(cit_key: str) -> str:
    """Create a filesystem-safe filename from a citation key."""
    return re.sub(r"[^\w\s\-]", "", cit_key).strip() or "untitled"


def run_sync() -> None:
    """Execute one sync pass (incremental or full)."""
    console.rule("[bold blue]Zotero → Obsidian Sync[/bold blue]")
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    sync_start = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    conn = connect()
    try:
        cursor = conn.cursor()

        last_sync = load_sync_state()
        if last_sync:
            console.print(f"🕐 Letzter Sync: [cyan]{last_sync}[/cyan]")
            changed_ids = get_changed_item_ids(cursor, last_sync)
            if changed_ids is not None:
                console.print(
                    f"🔍 Geänderte Items seit letztem Sync: [bold yellow]{len(changed_ids)}[/bold yellow]"
                )
                if not changed_ids:
                    console.print("[bold green]✅ Alles aktuell — nichts zu tun![/bold green]")
                    save_sync_state(sync_start)
                    return
            items = get_items(cursor, changed_ids)
        else:
            console.print("[yellow]⚡ Erster Sync — verarbeite ALLE Items[/yellow]")
            items = get_items(cursor)

        console.print(f"📚 Zu verarbeitende Einträge: [bold green]{len(items)}[/bold green]")

        written = 0
        for item in track(items, description="Verarbeite Papers..."):
            item_id, zotero_key, date_added, cit_key, title, abstract, authors = item
            if not cit_key:
                cit_key = zotero_key
                console.print(
                    f"[yellow]⚠️  Kein Citation Key für '{(title or 'Untitled')[:40]}', nutze: {zotero_key}[/yellow]"
                )

            safe_name = _safe_filename(cit_key)
            file_path = OUTPUT_FOLDER / f"{safe_name}.md"

            md_content = render_item_markdown(cursor, item)
            file_path.write_text(md_content, encoding="utf-8")
            written += 1

        # ── Handle deletions ──────────────────────────────────────────
        if last_sync:
            deleted_keys = get_deleted_item_keys(cursor, last_sync)
            deleted_count = 0
            for key in deleted_keys:
                for f in OUTPUT_FOLDER.glob("*.md"):
                    content = f.read_text(encoding="utf-8")
                    if f'zotero-key: "{key}"' in content:
                        f.unlink()
                        deleted_count += 1
                        console.print(f"[red]🗑️  Gelöscht: {f.name}[/red]")
            if deleted_count:
                console.print(f"[red]Gelöschte Dateien: {deleted_count}[/red]")

        save_sync_state(sync_start)
        console.print(f"\n[bold green]✅ Fertig![/bold green]")
        console.print(f"   📝 Geschrieben: {written}")
        console.print(f"   📂 Ordner: {OUTPUT_FOLDER}")

    except Exception:
        console.print_exception()
    finally:
        conn.close()