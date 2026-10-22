"""Markdown rendering — converts Zotero items to Obsidian-flavoured Markdown."""

from __future__ import annotations

import re

from markdownify import markdownify as md

from .database import (
    get_annotations,
    get_item_tags,
    get_notes,
    get_pdf_attachment_key,
)


# ── Helpers ────────────────────────────────────────────────────────────


def clean_text(text: str | None) -> str:
    """Strip residual HTML wrappers from a text fragment."""
    if not text:
        return ""
    return (
        text.replace("<div>", "")
        .replace("</div>", " ")
        .replace("<p>", "")
        .replace("</p>", "\n")
        .strip()
    )


def html_to_markdown(html_text: str | None) -> str:
    """Convert Zotero HTML notes to clean Markdown."""
    if not html_text:
        return ""
    markdown = md(html_text, heading_style="ATX", bullets="-", strong_em_symbol="*", strip=["span", "font"])
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = "\n".join(line.rstrip() for line in markdown.splitlines())
    return markdown.strip()


def format_authors_yaml(authors_str: str | None) -> str:
    """Format a semicolon-separated author list as a YAML array."""
    if not authors_str:
        return "[]"
    auth_list = [f'"{a.strip()}"' for a in authors_str.split(";")]
    return f"[{', '.join(auth_list)}]"


def format_tags_yaml(tags_list: list[str]) -> str:
    """Format tags as a YAML array, always including 'paper'."""
    all_tags = ["paper"] + tags_list
    cleaned = [t.strip().lower().replace(" ", "_").replace("-", "_") for t in all_tags]
    unique_tags = list(dict.fromkeys(cleaned))
    return "[" + ", ".join(unique_tags) + "]"


# ── Main render function ───────────────────────────────────────────────


def render_item_markdown(cursor, item) -> str:
    """
    Render a single Zotero item to a full Markdown document.

    The document includes YAML frontmatter, metadata, abstract,
    highlights/annotations, and Zotero notes.
    """
    item_id, zotero_key, date_added, cit_key, title, abstract, authors = item

    if not title:
        title = "Untitled"
    if not cit_key:
        cit_key = zotero_key

    item_tags = get_item_tags(cursor, item_id)
    tags_yaml = format_tags_yaml(item_tags)
    pdf_key = get_pdf_attachment_key(cursor, item_id)
    zotero_pdf_link = f"zotero://open-pdf/library/items/{pdf_key}" if pdf_key else ""
    zotero_item_link = f"zotero://select/library/items/{zotero_key}"

    # ── Annotations ───────────────────────────────────────────────────
    annotations_md = ""
    for text, comment, page, ann_key, att_key, ann_tags in get_annotations(cursor, item_id):
        loc = f" (p. {page})" if page else ""
        zotero_link = f"zotero://open-pdf/library/items/{att_key}?page={page}&annotation={ann_key}"
        text_block = (
            f'> [**"{clean_text(text)}"**]({zotero_link}){loc}\n'
            if text
            else f"> [**[Image/Highlight]**]({zotero_link}){loc}\n"
        )
        comment_block = f"> _↳ {clean_text(comment)}_\n" if comment else ""
        tags_block = ""
        if ann_tags:
            tags_formatted = " ".join(f"#{t.strip().lower().replace(' ', '_')}" for t in ann_tags.split(","))
            tags_block = f"> {tags_formatted}\n"
        annotations_md += f"{text_block}{comment_block}{tags_block}>\n"

    # ── Notes ─────────────────────────────────────────────────────────
    notes_md = ""
    notes = get_notes(cursor, item_id)
    for i, (note_html, note_added, note_modified) in enumerate(notes, 1):
        converted = html_to_markdown(note_html)
        if converted:
            if len(notes) > 1:
                notes_md += f"#### Notiz {i}\n*Erstellt: {note_added[:10]}*\n\n"
            notes_md += f"{converted}\n\n---\n\n"

    return f"""---
title: "{title}"
citation-key: "{cit_key}"
zotero-key: "{zotero_key}"
authors: {format_authors_yaml(authors)}
date-added: "{date_added}"
tags: {tags_yaml}
notes: {'true' if notes else 'false'}
---
# {title}
> [!cite] **{authors if authors else "Unknown Author"}**
> 🔑 [[{cit_key}]]
> 📅 {date_added}
> 🆔 {zotero_key}
> 📂 [In Zotero öffnen]({zotero_item_link})
> {f'📄 [PDF öffnen]({zotero_pdf_link})' if pdf_key else '📄 _Kein PDF vorhanden_'}
> #paper


---
### ◼ Abstract
> [!abstract] Summary
> {clean_text(abstract) if abstract else "No abstract available."}
---
### ◼ Highlights & Notes
{annotations_md if annotations_md else "*No annotations yet.*"}
---
### ◼ Zotero Notizen
{notes_md if notes_md else "*Keine Notizen vorhanden.*"}
"""