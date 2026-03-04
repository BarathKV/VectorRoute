import os
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple


# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HASH_DB_PATH = os.path.join(BASE_DIR, "hash_db.db")
CAPABILITIES_FOLDER = os.path.join(BASE_DIR, "VectorRoute-Tools", "capabilities")


def _init_db() -> sqlite3.Connection:
    """
    Create / connect to the SQLite hash database and ensure both tables exist:

    * ``file_hashes``  – stores the last-seen SHA-256 digest per tool.
    * ``change_log``   – append-only audit trail of every add / modify / delete.
    """
    conn = sqlite3.connect(HASH_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS file_hashes (
            tool_name TEXT PRIMARY KEY,
            hash      TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS change_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name   TEXT    NOT NULL,
            change_type TEXT    NOT NULL,
            old_hash    TEXT,
            new_hash    TEXT,
            file_path   TEXT,
            changed_at  TEXT    NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _compute_file_hash(file_path: str) -> str:
    """Return the SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _get_stored_hashes(conn: sqlite3.Connection) -> Dict[str, str]:
    """Return {tool_name: hash} for every row in the database."""
    rows = conn.execute("SELECT tool_name, hash FROM file_hashes").fetchall()
    return {name: h for name, h in rows}


# ── Public API ───────────────────────────────────────────────────────────────

def get_file_changes() -> Dict[str, Set[str]]:
    """
    Walk the capabilities folder, compare each .json file's hash against
    the SQLite database, and return a dict with three keys:

        {
            "added":    set of tool names that are new,
            "modified": set of tool names whose file changed,
            "deleted":  set of tool names no longer on disk,
        }
    """
    conn = _init_db()
    stored = _get_stored_hashes(conn)

    added: Set[str] = set()
    modified: Set[str] = set()
    seen: Set[str] = set()

    for root, _, files in os.walk(CAPABILITIES_FOLDER):
        for filename in files:
            if not filename.endswith(".json"):
                continue

            tool_name = os.path.splitext(filename)[0]
            file_path = os.path.join(root, filename)
            current_hash = _compute_file_hash(file_path)
            seen.add(tool_name)

            if tool_name not in stored:
                added.add(tool_name)
            elif stored[tool_name] != current_hash:
                modified.add(tool_name)

    deleted = set(stored.keys()) - seen

    conn.close()
    return {"added": added, "modified": modified, "deleted": deleted}


def update_hash_of_file(tool_name: str, file_path: str) -> None:
    """
    Compute the current hash of *file_path* and upsert into the SQLite
    database keyed by *tool_name*.
    """
    current_hash = _compute_file_hash(file_path)
    conn = _init_db()
    conn.execute(
        """
        INSERT INTO file_hashes (tool_name, hash)
        VALUES (?, ?)
        ON CONFLICT(tool_name) DO UPDATE SET hash = excluded.hash
        """,
        (tool_name, current_hash),
    )
    conn.commit()
    conn.close()


def log_change(
    tool_name: str,
    change_type: str,
    old_hash: Optional[str],
    new_hash: Optional[str],
    file_path: Optional[str],
) -> None:
    """
    Append one row to the ``change_log`` table.

    Args:
        tool_name:   Stem name of the capability JSON (e.g. ``"get_weather"``).
        change_type: One of ``"added"``, ``"modified"``, or ``"deleted"``.
        old_hash:    Previous SHA-256 digest; ``None`` for new tools.
        new_hash:    New SHA-256 digest; ``None`` for deleted tools.
        file_path:   Absolute path of the capability JSON; ``None`` when deleted.
    """
    conn = _init_db()
    conn.execute(
        """
        INSERT INTO change_log (tool_name, change_type, old_hash, new_hash, file_path, changed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            tool_name,
            change_type,
            old_hash,
            new_hash,
            file_path,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def delete_hash(tool_name: str) -> None:
    """
    Remove the ``file_hashes`` row for *tool_name* (called after a tool is
    deleted so future runs don't flag it as a missing entry).
    """
    conn = _init_db()
    conn.execute("DELETE FROM file_hashes WHERE tool_name = ?", (tool_name,))
    conn.commit()
    conn.close()


def get_recent_changes(n: int = 20) -> List[Tuple]:
    """
    Return the *n* most-recent rows from ``change_log``, ordered oldest-first.

    Each tuple: ``(id, tool_name, change_type, old_hash, new_hash, file_path, changed_at)``
    """
    conn = _init_db()
    rows = conn.execute(
        """
        SELECT id, tool_name, change_type, old_hash, new_hash, file_path, changed_at
        FROM change_log
        ORDER BY id DESC
        LIMIT ?
        """,
        (n,),
    ).fetchall()
    conn.close()
    return list(reversed(rows))
