import os
import sqlite3
import hashlib
import importlib.util
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple


# Paths (base_dir inferred from this file's parent)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "embedding_db", "file_hashes.db")


class FileTracker:
    """Tracks capability JSONs and function Python files.

    Behaviour summary:
    - Tracks files under `VectorRoute-Tools/capabilities` ("json") and
      `VectorRoute-Tools/functions` ("py").
    - Stores per-file hashes in an SQLite DB (one row per file key).
    - File keys are stored as: "json:<tool_name>" and "py:<tool_name>".
    - `get_file_changes()` returns a defaultdict(list) with keys
      `added`, `modified`, `deleted` listing tool names (stem names).
    - `get_tool_registry()` dynamically imports function modules and
      returns {tool_name: callable} for tools present on disk (both files).
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
        print(f"DEBUG: Capabilities folder set to: {self.capabilities_folder}")
        self.functions_folder = (
            functions_folder
            or os.path.join(self.base_dir, "VectorRoute-Tools", "functions")
        )
        print(f"DEBUG: Functions folder set to: {self.functions_folder}")
    # ---- Database helpers -------------------------------------------------
    def _init_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS file_hashes (
                file_key TEXT PRIMARY KEY,
                hash     TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS change_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                file_key    TEXT    NOT NULL,
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

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _get_stored_hashes(self, conn: sqlite3.Connection) -> Dict[str, str]:
        rows = conn.execute("SELECT file_key, hash FROM file_hashes").fetchall()
        return {key: h for key, h in rows}

    # ---- Public API -------------------------------------------------------
    def get_file_changes(self) -> defaultdict:
        """Return a defaultdict(list) with keys 'added','modified','deleted'.

        Tools are considered by their stem name (filename without suffix).
        A tool is classified as:
          - 'added'    : both .json and .py present now, but at least one file
                         has no previous DB entry
          - 'modified' : both present and at least one file's hash changed
          - 'deleted'  : previously tracked (any file_key in DB) but now one
                         or both files are missing on disk
        """
        conn = self._init_db()
        stored = self._get_stored_hashes(conn)

        # discover files on disk
        json_files: Dict[str, str] = {}
        for root, _, files in os.walk(self.capabilities_folder):
            for fn in files:
                if not fn.endswith(".json"):
                    continue
                name = os.path.splitext(fn)[0]
                json_files[name] = os.path.join(root, fn)

        py_files: Dict[str, str] = {}
        for root, _, files in os.walk(self.functions_folder):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                if fn.startswith("_"):
                    continue
                name = os.path.splitext(fn)[0]
                py_files[name] = os.path.join(root, fn)

        all_tools: Set[str] = set(json_files.keys()) | set(py_files.keys()) | {
            key.split(":", 1)[1] for key in stored.keys() if ":" in key
        }

        added: Set[str] = set()
        modified: Set[str] = set()
        deleted: Set[str] = set()

        for tool in all_tools:
            key_json = f"json:{tool}"
            key_py = f"py:{tool}"

            json_present = tool in json_files
            py_present = tool in py_files

            # file-level statuses
            file_added = False
            file_modified = False
            file_deleted = False

            # JSON file checks
            if json_present:
                cur = self._compute_file_hash(json_files[tool])
                if key_json not in stored:
                    file_added = True
                elif stored.get(key_json) != cur:
                    file_modified = True
            else:
                if key_json in stored:
                    file_deleted = True

            # PY file checks
            if py_present:
                cur = self._compute_file_hash(py_files[tool])
                if key_py not in stored:
                    file_added = True
                elif stored.get(key_py) != cur:
                    file_modified = True
            else:
                if key_py in stored:
                    file_deleted = True

            # Decide classification at tool-level
            if json_present and py_present:
                # both present now
                if file_added and not file_modified and not file_deleted:
                    added.add(tool)
                elif file_modified:
                    modified.add(tool)
            else:
                # One or both missing on disk -> if previously tracked, mark deleted
                if file_deleted or (not json_present and not py_present and (key_json in stored or key_py in stored)):
                    deleted.add(tool)
                else:
                    # partial presence (only one file present) and not previously tracked => added
                    if file_added:
                        added.add(tool)

            # Persist current state: upsert present files, remove missing files from file_hashes
            if json_present:
                self.update_hash_of_file(tool, json_files[tool], "json")
            else:
                if key_json in stored:
                    self.delete_hash(tool, "json")

            if py_present:
                self.update_hash_of_file(tool, py_files[tool], "py")
            else:
                if key_py in stored:
                    self.delete_hash(tool, "py")

        conn.close()

        result = defaultdict(list)
        result["added"] = sorted(list(added))
        result["modified"] = sorted(list(modified))
        result["deleted"] = sorted(list(deleted))
        return result

    def update_hash_of_file(self, tool_name: str, file_path: str, file_type: str) -> None:
        key = f"{file_type}:{tool_name}"
        current_hash = self._compute_file_hash(file_path)
        conn = self._init_db()
        old = conn.execute("SELECT hash FROM file_hashes WHERE file_key = ?", (key,)).fetchone()
        old_hash = old[0] if old else None
        conn.execute(
            "INSERT INTO file_hashes (file_key, hash) VALUES (?, ?) ON CONFLICT(file_key) DO UPDATE SET hash = excluded.hash",
            (key, current_hash),
        )
        conn.execute(
            "INSERT INTO change_log (file_key, change_type, old_hash, new_hash, file_path, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (key, "added" if old_hash is None else ("modified" if old_hash != current_hash else "unchanged"), old_hash, current_hash, file_path, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def log_change(self, file_key: str, change_type: str, old_hash: Optional[str], new_hash: Optional[str], file_path: Optional[str]) -> None:
        conn = self._init_db()
        conn.execute(
            "INSERT INTO change_log (file_key, change_type, old_hash, new_hash, file_path, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (file_key, change_type, old_hash, new_hash, file_path, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def delete_hash(self, tool_name: str, file_type: str) -> None:
        key = f"{file_type}:{tool_name}"
        conn = self._init_db()
        conn.execute("DELETE FROM file_hashes WHERE file_key = ?", (key,))
        conn.execute(
            "INSERT INTO change_log (file_key, change_type, old_hash, new_hash, file_path, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (key, "deleted", None, None, None, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def get_recent_changes(self, n: int = 20) -> List[Tuple]:
        conn = self._init_db()
        rows = conn.execute(
            "SELECT id, file_key, change_type, old_hash, new_hash, file_path, changed_at FROM change_log ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
        conn.close()
        return list(reversed(rows))

    # ---- Tool registry loader --------------------------------------------
    def get_tool_registry(self) -> Dict[str, callable]:
        """Dynamically import functions from the functions folder.

        Returns a dict mapping tool_name -> callable. Only includes tools
        which have both a `.json` capability and a `.py` function file on disk.
        """
        registry: Dict[str, callable] = {}

        # print(f"DEBUG: Capabilities folder: {self.capabilities_folder}")
        # print(f"DEBUG: Functions folder: {self.functions_folder}")

        # Build sets for matching
        json_files = {}
        for root, _, files in os.walk(self.capabilities_folder):
            for fn in files:
                if fn.endswith(".json"):
                    name = os.path.splitext(fn)[0]
                    json_files[name] = os.path.join(root, fn)

        # print(f"DEBUG: JSON files found: {json_files}")

        py_paths = []
        for root, _, files in os.walk(self.functions_folder):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                if fn.startswith("_"):
                    continue
                py_paths.append(os.path.join(root, fn))

        # print(f"DEBUG: Python files found: {py_paths}")

        for py_path in py_paths:
            # print(f"DEBUG: Processing function file: {py_path}")
            tool_name = os.path.splitext(os.path.basename(py_path))[0]
            if tool_name not in json_files:
                # print(f"DEBUG: Skipping {tool_name} as it has no matching JSON file.")
                continue
            # import module from file path
            module_name = os.path.relpath(py_path, self.functions_folder).replace(os.sep, ".")
            spec = importlib.util.spec_from_file_location(module_name, py_path)
            if spec is None or spec.loader is None:
                # print(f"DEBUG: Failed to create spec for {py_path}")
                continue
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                # print(f"DEBUG: Failed to import {py_path}: {e}")
                continue

            # prefer attribute with same name
            attr = getattr(module, tool_name, None)
            if callable(attr):
                registry[tool_name] = attr
                # print(f"DEBUG: Registered tool {tool_name} with callable {attr}")
                continue

            # fallback: first public callable in module
            for name in dir(module):
                if name.startswith("_"):
                    continue
                candidate = getattr(module, name)
                if callable(candidate):
                    registry[tool_name] = candidate
                    print(f"DEBUG: Registered tool {tool_name} with fallback callable {candidate}")
                    break

        # print(f"DEBUG: Final tool registry: {registry}")
        return registry

