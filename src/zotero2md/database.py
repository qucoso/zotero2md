"""Database layer — SQLite connection, queries, and sync-state management."""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from rich.console import Console

from .config import DB_MAIN, OUTPUT_FOLDER, SYNC_STATE_FILE

console = Console()


# ── Sync-state management ──────────────────────────────────────────────


def load_sync_state() -> str | None:
    """Load the last-sync timestamp from disk."""
    if SYNC_STATE_FILE.exists():
        try:
            data = json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
            return data.get("last_sync")
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def save_sync_state(timestamp: str) -> None:
    """Persist the current sync timestamp."""
    SYNC_STATE_FILE.write_text(
        json.dumps({"last_sync": timestamp, "synced_at": datetime.now().isoformat()}, indent=2),
        encoding="utf-8",
    )


# ── Database connection ────────────────────────────────────────────────


def connect() -> sqlite3.Connection:
    """
    Open a read-safe copy of the Zotero SQLite database.

    Zotero holds an exclusive lock on *zotero.sqlite* while it is running,
    so we copy the file to a temporary location first.
    """
    if not DB_MAIN.exists():
        raise FileNotFoundError(f"Zotero DB nicht gefunden unter {DB_MAIN}")

    tmp_path = Path(tempfile.gettempdir()) / "zotero_tmp.sqlite"
    shutil.copy2(DB_MAIN, tmp_path)
    return sqlite3.connect(tmp_path)


# ── Queries ────────────────────────────────────────────────────────────


def get_changed_item_ids(cursor: sqlite3.Cursor, since_timestamp: str) -> set[int] | None:
    """
    Find all item IDs that changed since the last sync.

    Checks changes to:
    1. The item itself (dateModified / clientDateModified)
    2. Annotations (dateModified of annotation items)
    3. Notes (dateModified of note items)
    4. Attachments (dateModified)

    Returns ``None`` when *since_timestamp* is ``None`` (i.e. first run → full sync).
    """
    if since_timestamp is None:
        return None  # None = process ALL items

    query = """
    -- Items changed directly
    SELECT DISTINCT items.itemID
    FROM items
    JOIN itemTypes ON items.itemTypeID = itemTypes.itemTypeID
    WHERE itemTypes.typeName NOT IN ('attachment', 'note', 'annotation')
      AND items.itemID NOT IN (SELECT itemID FROM deletedItems)
      AND items.dateModified > ?

    UNION

    -- Items whose annotations changed
    SELECT DISTINCT att_data.parentItemID
    FROM itemAnnotations ia
    JOIN items ann_item ON ia.itemID = ann_item.itemID
    JOIN itemAttachments att_data ON ia.parentItemID = att_data.itemID
    WHERE ann_item.dateModified > ?
      AND att_data.parentItemID IS NOT NULL

    UNION

    -- Items whose notes changed
    SELECT DISTINCT itemNotes.parentItemID
    FROM itemNotes
    JOIN items ON itemNotes.itemID = items.itemID
    WHERE items.dateModified > ?
      AND itemNotes.parentItemID IS NOT NULL

    UNION

    -- Items whose attachments changed
    SELECT DISTINCT itemAttachments.parentItemID
    FROM itemAttachments
    JOIN items ON itemAttachments.itemID = items.itemID
    WHERE items.dateModified > ?
      AND itemAttachments.parentItemID IS NOT NULL

    UNION

    -- Items touched (clientDateModified)
    SELECT DISTINCT items.itemID
    FROM items
    JOIN itemTypes ON items.itemTypeID = itemTypes.itemTypeID
    WHERE itemTypes.typeName NOT IN ('attachment', 'note', 'annotation')
      AND items.itemID NOT IN (SELECT itemID FROM deletedItems)
      AND items.clientDateModified > ?
    """
    cursor.execute(query, (since_timestamp,) * 5)
    return {row[0] for row in cursor.fetchall()}


def get_deleted_item_keys(cursor: sqlite3.Cursor, since_timestamp: str) -> set[str]:
    """Return Zotero keys of items deleted since *since_timestamp*."""
    if since_timestamp is None:
        return set()

    query = """
    SELECT items.key
    FROM deletedItems
    JOIN items ON deletedItems.itemID = items.itemID
    WHERE items.dateModified > ?
    """
    cursor.execute(query, (since_timestamp,))
    return {row[0] for row in cursor.fetchall()}


def get_items(cursor: sqlite3.Cursor, item_ids_filter: set[int] | None = None) -> list[tuple]:
    """
    Fetch metadata items from the Zotero database.

    Parameters
    ----------
    item_ids_filter
        If provided, only items with these IDs are returned (incremental sync).
        If ``None``, all items are returned (full sync).
    """
    base_query = """
    SELECT
        items.itemID,
        items.key AS zotero_key,
        items.dateAdded,
        (SELECT value FROM itemData
         JOIN itemDataValues USING(valueID)
         JOIN fields USING(fieldID)
         WHERE itemID=items.itemID AND fieldName='citationKey') AS citation_key,
        (SELECT value FROM itemData
         JOIN itemDataValues USING(valueID)
         JOIN fields USING(fieldID)
         WHERE itemID=items.itemID AND fieldName='title') AS title,
        (SELECT value FROM itemData
         JOIN itemDataValues USING(valueID)
         JOIN fields USING(fieldID)
         WHERE itemID=items.itemID AND fieldName='abstractNote') AS abstract,
        (SELECT GROUP_CONCAT(c.lastName || ', ' || c.firstName, '; ')
         FROM itemCreators ic
         JOIN creators c ON ic.creatorID = c.creatorID
         WHERE ic.itemID = items.itemID
         ORDER BY ic.orderIndex) AS authors
    FROM items
    JOIN itemTypes ON items.itemTypeID = itemTypes.itemTypeID
    WHERE itemTypes.typeName NOT IN ('attachment', 'note', 'annotation')
      AND items.itemID NOT IN (SELECT itemID FROM deletedItems)
    """

    if item_ids_filter is not None:
        if not item_ids_filter:
            return []
        placeholders = ",".join("?" * len(item_ids_filter))
        base_query += f" AND items.itemID IN ({placeholders})"
        cursor.execute(base_query, list(item_ids_filter))
    else:
        cursor.execute(base_query)

    return cursor.fetchall()


def get_annotations(cursor: sqlite3.Cursor, item_id: int) -> list[tuple]:
    """Fetch all annotations for a given Zotero item."""
    query = """
    SELECT ia.text, ia.comment, ia.pageLabel,
           ann_item.key, att_item.key,
           (SELECT GROUP_CONCAT(t.name, ', ')
            FROM itemTags it JOIN tags t ON it.tagID = t.tagID
            WHERE it.itemID = ia.itemID) AS ann_tags
    FROM itemAnnotations ia
    JOIN itemAttachments att_data ON ia.parentItemID = att_data.itemID
    JOIN items att_item ON att_data.itemID = att_item.itemID
    JOIN items ann_item ON ia.itemID = ann_item.itemID
    WHERE att_data.parentItemID = ?
    """
    cursor.execute(query, (item_id,))
    return cursor.fetchall()


def get_notes(cursor: sqlite3.Cursor, item_id: int) -> list[tuple]:
    """Fetch all notes attached to a given Zotero item."""
    query = """
    SELECT itemNotes.note, items.dateAdded, items.dateModified
    FROM itemNotes
    JOIN items ON itemNotes.itemID = items.itemID
    WHERE itemNotes.parentItemID = ?
    ORDER BY items.dateAdded
    """
    cursor.execute(query, (item_id,))
    return cursor.fetchall()


def get_item_tags(cursor: sqlite3.Cursor, item_id: int) -> list[str]:
    """Fetch all tags for a given Zotero item."""
    query = """
    SELECT t.name FROM itemTags it
    JOIN tags t ON it.tagID = t.tagID
    WHERE it.itemID = ?
    """
    cursor.execute(query, (item_id,))
    return [row[0] for row in cursor.fetchall()]


def get_pdf_attachment_key(cursor: sqlite3.Cursor, item_id: int) -> str | None:
    """Return the Zotero key of the first PDF attachment for *item_id*."""
    query = """
    SELECT items.key FROM itemAttachments
    JOIN items ON itemAttachments.itemID = items.itemID
    WHERE itemAttachments.parentItemID = ?
      AND itemAttachments.contentType = 'application/pdf'
    LIMIT 1
    """
    cursor.execute(query, (item_id,))
    result = cursor.fetchone()
    return result[0] if result else None