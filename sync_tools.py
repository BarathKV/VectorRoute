"""
sync_tools.py
─────────────
Standalone script that keeps the SQLite hash DB and ChromaDB in sync with
every change made to ``VectorRoute-Tools/capabilities/**/*.json`` files.

Flow
────
1. Walk the capabilities folder and compare each file's SHA-256 hash against
   the ``file_hashes`` table in ``db/chroma_db.db``.
2. Classify every file as **added**, **modified**, or **deleted**.
3. Append one row per change to the ``change_log`` table (audit trail).
4. For each added tool   → embed & index in ChromaDB, then update hash row.
5. For each modified tool → delete old embeddings, re-index, then update hash.
6. For each deleted tool  → remove embeddings from ChromaDB, delete hash row.

Usage
─────
    python sync_tools.py              # full sync
    python sync_tools.py --dry-run    # detect changes without writing anything
    python sync_tools.py --log        # print the 20 most-recent change-log rows
    python sync_tools.py --log --n 50 # print the 50 most-recent rows
"""

import argparse
import json
import os
import sys

import chromadb

from embedding.embedder import get_embedding
from tools.file_tracker import (
    CAPABILITIES_FOLDER,
    HASH_DB_PATH,
    _compute_file_hash,
    _get_stored_hashes,
    _init_db,
    delete_hash,
    get_file_changes,
    get_recent_changes,
    log_change,
    update_hash_of_file,
)

# ── ChromaDB config (mirrors db_connection.py) ───────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "embedding_db")
COLLECTION_NAME = "tool_embeddings"


# ── ChromaDB helpers ──────────────────────────────────────────────────────────

def _get_collection(similarity: str = "cosine"):
    """Return (or create) the persistent ChromaDB collection."""
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    col = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": similarity},
    )
    print(f"ChromaDB ready - '{COLLECTION_NAME}' ({col.count()} entries)")
    return col


def _chroma_add(collection, tool_name: str, tool_data: dict) -> None:
    """
    Embed every semantic facet of *tool_data* and insert into ChromaDB.

    One vector per example user query  (category: ``example_query``)
    One vector for the short description (category: ``description``)
    One vector for the long description  (category: ``long_description``)
    One vector for the domain label      (category: ``domain``)
    """
    import uuid

    func = tool_data.get("function", {})
    examples: list = func.get("example_user_queries", [])
    description: str = func.get("description", "")
    long_description: str = func.get("long_description", "")
    domain: str = func.get("domain", "")

    for example in examples:
        collection.add(
            ids=[f"{tool_name}_{uuid.uuid4().hex}"],
            embeddings=[get_embedding(example)],
            metadatas=[{"tool": tool_name, "category": "example_query"}],
        )

    collection.add(
        ids=[f"{tool_name}_desc"],
        embeddings=[get_embedding(description)],
        metadatas=[{"tool": tool_name, "category": "description"}],
    )

    collection.add(
        ids=[f"{tool_name}_long_desc"],
        embeddings=[get_embedding(long_description)],
        metadatas=[{"tool": tool_name, "category": "long_description"}],
    )

    collection.add(
        ids=[f"{tool_name}_domain"],
        embeddings=[get_embedding(domain)],
        metadatas=[{"tool": tool_name, "category": "domain"}],
    )

    print(f"  [+] ChromaDB: added '{tool_name}' ({len(examples)} example queries)")


def _chroma_delete(collection, tool_name: str) -> None:
    """Remove every ChromaDB entry that belongs to *tool_name*."""
    existing = collection.get(where={"tool": tool_name}, include=[])
    ids = existing["ids"] if existing else []
    if ids:
        collection.delete(ids=ids)
    print(f"  [-] ChromaDB: deleted '{tool_name}' ({len(ids)} entries removed)")


def _chroma_update(collection, tool_name: str, tool_data: dict) -> None:
    """Delete all existing entries for *tool_name* and re-index from scratch."""
    _chroma_delete(collection, tool_name)
    _chroma_add(collection, tool_name, tool_data)
    print(f"  [~] ChromaDB: updated '{tool_name}'")


# ── Capability file loader ────────────────────────────────────────────────────

def _load_tool_docs_map() -> dict:
    """
    Walk the capabilities folder and return::

        { tool_name: (parsed_json_dict, absolute_file_path, sha256_hash) }
    """
    tool_map: dict = {}
    for root, _, files in os.walk(CAPABILITIES_FOLDER):
        for fname in files:
            if not fname.endswith(".json"):
                continue
            tool_name = os.path.splitext(fname)[0]
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r") as fh:
                    tool_map[tool_name] = (
                        json.load(fh),
                        fpath,
                        _compute_file_hash(fpath),
                    )
            except json.JSONDecodeError:
                print(f"  ⚠  Skipping invalid JSON: {fpath}")
    return tool_map


# ── Core sync logic ───────────────────────────────────────────────────────────

def sync(dry_run: bool = False) -> None:
    """
    Detect capability-file changes, record them in SQLite, and sync ChromaDB.

    Args:
        dry_run: When ``True`` the function prints what *would* happen but does
                 not write to SQLite or ChromaDB.
    """
    # ── Step 1: detect changes ────────────────────────────────────────────────
    changes = get_file_changes()
    added    = sorted(changes["added"])
    modified = sorted(changes["modified"])
    deleted  = sorted(changes["deleted"])

    total = len(added) + len(modified) + len(deleted)

    if total == 0:
        print("✓ No capability changes detected - everything is up to date.")
        return

    # Pretty summary
    _sep = "─" * 60
    print(f"\n{_sep}")
    print(
        f"Changes detected → "
        f"added={len(added)}  modified={len(modified)}  deleted={len(deleted)}"
    )
    for name in added:    print(f"  [+] {name}")
    for name in modified: print(f"  [~] {name}")
    for name in deleted:  print(f"  [-] {name}")
    print(_sep)

    if dry_run:
        print("\n[dry-run] No changes written.")
        return

    # ── Step 2: load docs & stored hashes once ────────────────────────────────
    tool_docs     = _load_tool_docs_map()          # { tool_name: (data, path, hash) }
    stored_hashes = _get_stored_hashes(_init_db()) # { tool_name: old_hash }
    collection    = _get_collection()

    print()

    # ── Step 3: process added tools ───────────────────────────────────────────
    for tool_name in added:
        if tool_name not in tool_docs:
            print(f"  ⚠  '{tool_name}' flagged as added but not found on disk - skipping")
            continue
        tool_data, file_path, new_hash = tool_docs[tool_name]

        _chroma_add(collection, tool_name, tool_data)
        log_change(tool_name, "added", old_hash=None, new_hash=new_hash, file_path=file_path)
        update_hash_of_file(tool_name, file_path)

    # ── Step 4: process modified tools ────────────────────────────────────────
    for tool_name in modified:
        if tool_name not in tool_docs:
            print(f"  ⚠  '{tool_name}' flagged as modified but not found on disk - skipping")
            continue
        tool_data, file_path, new_hash = tool_docs[tool_name]
        old_hash = stored_hashes.get(tool_name)

        _chroma_update(collection, tool_name, tool_data)
        log_change(tool_name, "modified", old_hash=old_hash, new_hash=new_hash, file_path=file_path)
        update_hash_of_file(tool_name, file_path)

    # ── Step 5: process deleted tools ─────────────────────────────────────────
    for tool_name in deleted:
        old_hash = stored_hashes.get(tool_name)

        _chroma_delete(collection, tool_name)
        log_change(tool_name, "deleted", old_hash=old_hash, new_hash=None, file_path=None)
        delete_hash(tool_name)  # remove stale row so it won't re-appear

    print(
        f"\n✓ Sync complete - "
        f"added={len(added)}  modified={len(modified)}  deleted={len(deleted)}"
    )


# ── Change log viewer ─────────────────────────────────────────────────────────

def show_log(n: int = 20) -> None:
    """Print the *n* most-recent change-log rows in a readable table."""
    rows = get_recent_changes(n)
    if not rows:
        print("No change log entries found.")
        return

    _sep  = "─" * 90
    _fmt  = "{:>4}  {:<35}  {:<10}  {:<28}  {}"
    print(f"\n{_sep}")
    print(_fmt.format("ID", "Tool Name", "Type", "Changed At (UTC)", "File Path"))
    print(_sep)
    for row in rows:
        rid, tool_name, change_type, _old, _new, file_path, changed_at = row
        fp_display = os.path.relpath(file_path, BASE_DIR) if file_path else "(deleted)"
        print(_fmt.format(rid, tool_name, change_type, changed_at, fp_display))
    print(_sep)
    print(f"Showing {len(rows)} of the most-recent change-log entries.\n")


# ── CLI entry point ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sync_tools",
        description=(
            "Sync VectorRoute-Tools capability JSON files with SQLite (hash + change_log) "
            "and ChromaDB."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect and print changes without writing anything.",
    )
    p.add_argument(
        "--log",
        action="store_true",
        help="Print recent change-log entries from SQLite and exit.",
    )
    p.add_argument(
        "--n",
        type=int,
        default=20,
        metavar="N",
        help="Number of recent log entries to show with --log (default: 20).",
    )
    return p


if __name__ == "__main__":
    args = _build_parser().parse_args()

    if args.log:
        show_log(args.n)
    else:
        sync(dry_run=args.dry_run)
