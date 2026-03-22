import os
import sqlite3
import hashlib
import importlib.util
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Callable
import time


# Paths (base_dir inferred from this file's parent)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "embedding_db", "file_hashes.db")


class FileTracker:
    """Tracks capability JSONs and function Python files.

    Behaviour summary:
    - Tracks files under `VectorRoute-Tools/capabilities` ("json") and
      `VectorRoute-Tools/functions` ("py").
    - Stores per-file hashes in an SQLite DB (one row per file key).
    - Dynamically builds an in-memory tool registry.
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        db_path: Optional[str] = None,
        capabilities_folder: Optional[str] = None,
        functions_folder: Optional[str] = None,
    ) -> None:
        self.base_dir = base_dir or BASE_DIR
        self.db_path = db_path or DEFAULT_DB_PATH
        self.capabilities_folder = (
            capabilities_folder
            or os.path.join(self.base_dir, "VectorRoute-Tools", "capabilities")
        )
        self.functions_folder = (
            functions_folder
            or os.path.join(self.base_dir, "VectorRoute-Tools", "functions")
        )

    # ---- Database helpers -------------------------------------------------
    def _init_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)  # Increased timeout to handle longer waits
        conn.execute("PRAGMA journal_mode=WAL;")  # Enable Write-Ahead Logging for better concurrency
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tools (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                file_path TEXT,
                hash TEXT,
                module TEXT,
                function_name TEXT,
                last_loaded TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS change_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_key TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_hash TEXT,
                new_hash TEXT,
                file_path TEXT,
                changed_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        return conn

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def log_change(
        self,
        file_key: str,
        change_type: str,
        old_hash: Optional[str],
        new_hash: Optional[str],
        file_path: Optional[str],
    ) -> None:
        """Log changes to the change_log table with retry logic."""
        retries = 10  # Increased retries to handle persistent locks
        while retries > 0:
            try:
                conn = self._init_db()
                conn.execute(
                    "INSERT INTO change_log (file_key, change_type, old_hash, new_hash, file_path, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (file_key, change_type, old_hash, new_hash, file_path, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
                conn.close()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    retries -= 1
                    print(f"DEBUG: Database is locked. Retrying... ({10 - retries}/10)")
                    time.sleep(2 ** (10 - retries))  # Exponential backoff
                else:
                    raise
            finally:
                if 'conn' in locals() and conn:
                    conn.close()

    # ---- Tool Registry ----------------------------------------------------
    @staticmethod
    def _load_function(file_path: str, function_name: str = "main") -> Callable:
        """Dynamically load a function from a Python file."""
        spec = importlib.util.spec_from_file_location("tool_module", file_path)
        module = importlib.util.module_from_spec(spec)
        if file_path in sys.modules:
            del sys.modules[file_path]  # Avoid stale imports
        sys.modules[file_path] = module
        spec.loader.exec_module(module)
        return getattr(module, function_name)

    @staticmethod
    def build_tool_registry(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Callable]:
        """Build an in-memory tool registry from the SQLite database."""
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT name, file_path, function_name FROM tools").fetchall()
        conn.close()

        registry = {}
        for name, file_path, function_name in rows:
            try:
                registry[name] = FileTracker._load_function(file_path, function_name)
            except Exception as e:
                print(f"WARNING: Failed to load tool {name} from {file_path}: {e}")
        return registry

    # ---- File Change Detection --------------------------------------------
    def get_file_changes(self) -> defaultdict:
        """Detect file changes and update the SQLite database."""
        conn = self._init_db()
        stored = {
            row["name"]: row for row in conn.execute("SELECT name, file_path, hash FROM tools").fetchall()
        }

        # Discover files on disk
        py_files = {}
        for root, _, files in os.walk(self.functions_folder):
            for fn in files:
                if not fn.endswith(".py") or fn.startswith("_"):
                    continue
                name = os.path.splitext(fn)[0]
                py_files[name] = os.path.join(root, fn)

        added, modified, deleted = set(), set(), set()

        for name, file_path in py_files.items():
            cur_hash = self._compute_file_hash(file_path)
            if name not in stored:
                added.add(name)
                conn.execute(
                    "INSERT INTO tools (name, file_path, hash, module, function_name, last_loaded) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, file_path, cur_hash, None, "main", datetime.now(timezone.utc).isoformat()),
                )
                self.log_change(f"py:{name}", "added", None, cur_hash, file_path)
            elif stored[name]["hash"] != cur_hash:
                modified.add(name)
                conn.execute(
                    "UPDATE tools SET hash = ?, last_loaded = ? WHERE name = ?",
                    (cur_hash, datetime.now(timezone.utc).isoformat(), name),
                )
                self.log_change(f"py:{name}", "modified", stored[name]["hash"], cur_hash, file_path)

        for name in stored:
            if name not in py_files:
                deleted.add(name)
                conn.execute("DELETE FROM tools WHERE name = ?", (name,))
                self.log_change(f"py:{name}", "deleted", stored[name]["hash"], None, stored[name]["file_path"])

        conn.commit()
        conn.close()

        result = defaultdict(list)
        result["added"] = sorted(list(added))
        result["modified"] = sorted(list(modified))
        result["deleted"] = sorted(list(deleted))
        return result

