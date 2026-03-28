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
        self.conn = self._init_db()  # Initialize the database connection

    # ---- Database helpers -------------------------------------------------
    def _init_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)  # Increased timeout to handle longer waits
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
        """Log changes to the change_log table."""
        self.conn.execute(
            "INSERT INTO change_log (file_key, change_type, old_hash, new_hash, file_path, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (file_key, change_type, old_hash, new_hash, file_path, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    # ---- Tool Registry ----------------------------------------------------
    @staticmethod
    def _load_function(file_path: str, function_name: str = "main") -> Callable:
        """Dynamically load a function from a Python file, with a fallback to the first callable."""
        module_name = os.path.splitext(os.path.relpath(file_path, BASE_DIR))[0]
        module_name = module_name.replace(os.sep, '.')  # Convert path to module name

        # Dynamically import the module
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Try to get the specified function
        if hasattr(module, function_name):
            return getattr(module, function_name)

        # Fallback: Return the first callable in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and not attr_name.startswith("_"):
                print(f"WARNING: Function '{function_name}' not found in {file_path}. Using fallback '{attr_name}'.")
                return attr

        raise AttributeError(f"No callable found in module '{module_name}' at {file_path}.")

    # @staticmethod
    # def build_tool_registry(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Callable]:
    #     """Build an in-memory tool registry from the SQLite database."""
    #     conn = sqlite3.connect(db_path)
    #     rows = conn.execute("SELECT name, file_path, function_name FROM tools").fetchall()
    #     conn.close()

    #     registry = {}
    #     for name, file_path, function_name in rows:
    #         try:
    #             registry[name] = FileTracker._load_function(file_path, function_name)
    #         except Exception as e:
    #             print(f"WARNING: Failed to load tool {name} from {file_path}: {e}")
    #     return registry

    @staticmethod
    def get_tool_registry() -> Dict[str, callable]:
        """Dynamically import functions from the functions folder.

        Returns a dict mapping tool_name -> callable. Only includes tools
        which have both a `.json` capability and a `.py` function file on disk.
        """
        registry: Dict[str, callable] = {}

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        capabilities_folder = os.path.join(base_dir, "VectorRoute-Tools", "capabilities")
        print(f"DEBUG: Capabilities folder set to: {capabilities_folder}")
        functions_folder = os.path.join(base_dir, "VectorRoute-Tools", "functions")
        print(f"DEBUG: Functions folder set to: {functions_folder}")

        # Build sets for matching
        json_files = {}
        for root, _, files in os.walk(capabilities_folder):
            for fn in files:
                if fn.endswith(".json"):
                    name = os.path.splitext(fn)[0]
                    json_files[name] = os.path.join(root, fn)

        py_paths = []
        for root, _, files in os.walk(functions_folder):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                if fn.startswith("_"):
                    continue
                py_paths.append(os.path.join(root, fn))

        for py_path in py_paths:
            tool_name = os.path.splitext(os.path.basename(py_path))[0]
            if tool_name not in json_files:
                continue

            # Import module from file path
            module_name = os.path.relpath(py_path, functions_folder).replace(os.sep, ".")
            spec = importlib.util.spec_from_file_location(module_name, py_path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                continue

            # Prefer attribute with same name
            attr = getattr(module, tool_name, None)
            if callable(attr):
                registry[tool_name] = attr
                continue

            # Fallback: first public callable in module
            for name in dir(module):
                if name.startswith("_"):
                    continue
                candidate = getattr(module, name)
                if callable(candidate):
                    registry[tool_name] = candidate
                    print(f"DEBUG: Registered tool {tool_name} with fallback callable {candidate}")
                    break
        print(f"Built tool registry with {len(registry)} tools: {list(registry.keys())}")
        return registry

    def get_file_changes(self) -> defaultdict:
        """Detect file changes and update the SQLite database."""

        # stored = {
        #     row["name"]: row for row in self.conn.execute("SELECT name, file_path, hash FROM tools").fetchall()
        # }

        stored = self.conn.execute("SELECT name, file_path, hash FROM tools").fetchall()
        stored = {row[0]: {"file_path": row[1], "hash": row[2]} for row in stored}

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
                self.conn.execute(
                    "INSERT INTO tools (name, file_path, hash, module, function_name, last_loaded) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, file_path, cur_hash, None, "main", datetime.now(timezone.utc).isoformat()),
                )
                self.log_change(f"py:{name}", "added", None, cur_hash, file_path)
            elif stored[name]["hash"] != cur_hash:
                modified.add(name)
                self.conn.execute(
                    "UPDATE tools SET hash = ?, last_loaded = ? WHERE name = ?",
                    (cur_hash, datetime.now(timezone.utc).isoformat(), name),
                )
                self.log_change(f"py:{name}", "modified", stored[name]["hash"], cur_hash, file_path)

        for name in stored:
            if name not in py_files:
                deleted.add(name)
                self.conn.execute("DELETE FROM tools WHERE name = ?", (name,))
                self.log_change(f"py:{name}", "deleted", stored[name]["hash"], None, stored[name]["file_path"])

        # # Update hashes for all files before returning the result
        # for name, file_path in py_files.items():
        #     self.update_hash_of_file(name, file_path, "py")

        self.conn.commit()

        result = defaultdict(list)
        result["added"] = sorted(list(added))
        result["modified"] = sorted(list(modified))
        result["deleted"] = sorted(list(deleted))
        print(f"File change detection result: {result}")
        return result

    def close_connection(self) -> None:
        """Close the database connection when done."""
        if self.conn:
            self.conn.close()

