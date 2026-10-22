"""CLI entry point — run with ``python -m zotero2md`` or the ``zotero2md`` console script."""


from .sync import run_sync


def main() -> None:
    """Console-script entry point."""
    run_sync()


if __name__ == "__main__":
    main()