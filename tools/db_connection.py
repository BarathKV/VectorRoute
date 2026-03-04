import os
import json
import uuid
import chromadb
from collections import Counter

from embedding.embedder import get_embedding
from tools.fetch_tool_docs import fetch_tool_docs
from tools.file_tracker import (
    get_file_changes,
    update_hash_of_file,
    CAPABILITIES_FOLDER,
)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "embeding_db")
COLLECTION_NAME = "tool_embeddings"


class DBConnection:
    """
    Manages a persistent ChromaDB collection that stores one embedding
    per tool (keyed by the tool name from its capability JSON).
    """

    def __init__(
        self, db_path: str = CHROMA_DB_PATH, similarity_methods: str = "cosine"
    ):
        """
        Establish a persistent ChromaDB client and get/create the
        tool_embeddings collection.
        """
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": similarity_methods},
        )
        print(
            f"ChromaDB connected - collection '{COLLECTION_NAME}' "
            f"({self.collection.count()} tools stored)"
        )

    # ── Private helpers ──────────────────────────────────────────────────

    def _build_document(self, tool_data: dict) -> str:
        """
        Turn a capability JSON dict into the text that will be embedded.
        Uses the function name + description + parameter descriptions.
        """
        func = tool_data.get("function", {})
        parts = [
            func.get("name", ""),
            func.get("description", ""),
        ]
        params = func.get("parameters", {}).get("properties", {})
        for param_name, param_info in params.items():
            parts.append(f"{param_name}: {param_info.get('description', '')}")
        return " | ".join(parts)

    def _add_tool(self, tool_name: str, tool_data: dict) -> None:
        """
        Index all semantic facets of a tool into the ChromaDB collection:

        - One entry per example user query  (category: ``example_query``)
        - One entry for the short description (category: ``description``)
        - One entry for the long description  (category: ``long_description``)
        - One entry for the domain label      (category: ``domain``)
        """
        func = tool_data.get("function", {})
        examples: list = func.get("example_user_queries", [])
        description: str = func.get("description", "")
        long_description: str = func.get("long_description", "")
        domain: str = func.get("domain", "")

        # Example queries – each gets a unique id
        for example in examples:
            self.collection.add(
                ids=[f"{tool_name}_{uuid.uuid4().hex}"],
                embeddings=[get_embedding(example)],
                metadatas=[{"tool": tool_name, "category": "example_query"}],
            )

        # Short description
        self.collection.add(
            ids=[f"{tool_name}_desc"],
            embeddings=[get_embedding(description)],
            metadatas=[{"tool": tool_name, "category": "description"}],
        )

        # Long description
        self.collection.add(
            ids=[f"{tool_name}_long_desc"],
            embeddings=[get_embedding(long_description)],
            metadatas=[{"tool": tool_name, "category": "long_description"}],
        )

        # Domain
        self.collection.add(
            ids=[f"{tool_name}_domain"],
            embeddings=[get_embedding(domain)],
            metadatas=[{"tool": tool_name, "category": "domain"}],
        )

        print(f"  [+] Added tool: {tool_name} ({len(examples)} examples)")

    def _update_tool(self, tool_name: str, tool_data: dict) -> None:
        """
        Update all ChromaDB entries for *tool_name*:

        1. Delete every existing entry that belongs to this tool
           (example queries via metadata filter + the fixed-id entries).
        2. Re-index via :meth:`_add_tool` so all categories are fresh.
        """
        self._delete_tool(tool_name)
        self._add_tool(tool_name, tool_data)
        print(f"  [~] Updated tool: {tool_name}")

    def _delete_tool(self, tool_name: str) -> None:
        """
        Remove every ChromaDB entry that belongs to *tool_name*:

        - Fixed-id entries: ``{tool_name}_desc``, ``{tool_name}_long_desc``,
          ``{tool_name}_domain``.
        - Variable-id example entries: queried via ``where={"tool": tool_name}``
          and deleted in bulk.
        """
        # Delete all entries tagged with this tool (covers example_query entries
        # whose ids contain a uuid and cannot be predicted)
        existing = self.collection.get(
            where={"tool": tool_name},
            include=[],  # only ids are needed
        )
        if existing and existing["ids"]:
            self.collection.delete(ids=existing["ids"])

        print(f"  [-] Deleted tool: {tool_name} ({len(existing['ids'])} entries)")

    # ── Public API ───────────────────────────────────────────────────────

    def update_db(self) -> None:
        """
        Synchronise ChromaDB with the capability JSON files on disk.

        1. Call *get_file_changes()* to find added / modified / deleted tools.
        2. For each added tool   → _add_tool()   + update hash in SQLite.
        3. For each modified tool → _update_tool() + update hash in SQLite.
        4. For each deleted tool  → _delete_tool() (hash row stays or can be
           pruned separately).
        """
        changes = get_file_changes()
        added = changes["added"]
        modified = changes["modified"]
        deleted = changes["deleted"]

        if not (added or modified or deleted):
            print("No capability changes detected - ChromaDB is up to date.")
            return

        # Build a {tool_name: tool_data} lookup from the capability files
        tool_docs = self._load_tool_docs_map()

        for tool_name in added:
            if tool_name in tool_docs:
                tool_data, file_path = tool_docs[tool_name]
                self._add_tool(tool_name, tool_data)
                update_hash_of_file(tool_name, file_path)

        for tool_name in modified:
            if tool_name in tool_docs:
                tool_data, file_path = tool_docs[tool_name]
                self._update_tool(tool_name, tool_data)
                update_hash_of_file(tool_name, file_path)

        for tool_name in deleted:
            self._delete_tool(tool_name)

        print(
            f"Sync complete  ➜  added={len(added)}  "
            f"modified={len(modified)}  deleted={len(deleted)}"
        )

    def route_query(
        self,
        user_query: str,
        top_k: int = 10,
        threshold: float = 0.7,
        min_example_hits: int = 4,
    ) -> str:
        """
        Route a user query to the best-matching tool using a two-step
        strategy:

        1. **Example-query search** - retrieve the *top_k* nearest
           neighbours whose ``category`` metadata is ``"example_query"``.
           Count how often each tool appears.
        2. **Validation** - for every tool that appears ≥ *min_example_hits*
           times, run a second query restricted to that tool's
           ``description``, ``long_description`` and ``domain`` entries.
           If every validation distance converts to a similarity above
           *threshold* the tool is returned.

        Returns the matched tool name, or ``"No confident match"``.
        """
        user_embedding = get_embedding(user_query)

        # ── Step 1: search only example queries ──────────────────────
        results = self.collection.query(
            query_embeddings=[user_embedding],
            n_results=top_k,
            where={"category": "example_query"},
        )

        tools_found = [m["tool"] for m in results["metadatas"][0]]
        count = Counter(tools_found)

        # ── Step 2: find tool with enough example matches ────────────
        for tool_name, c in count.items():
            if c >= min_example_hits:

                # ── Step 3: validate against other categories ────────
                validation = self.collection.query(
                    query_embeddings=[user_embedding],
                    n_results=3,
                    where={
                        "$and": [
                            {"tool": tool_name},
                            {
                                "category": {
                                    "$in": [
                                        "description",
                                        "long_description",
                                        "domain",
                                    ]
                                }
                            },
                        ]
                    },
                )

                distances = validation["distances"][0]

                if all(1 - d > threshold for d in distances):
                    return tool_name

        return "No confident match"

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _load_tool_docs_map() -> dict:
        """
        Walk the capabilities folder and return a dict::

            { tool_name: (parsed_json, file_path) }
        """
        tool_map: dict = {}
        for root, _, files in os.walk(CAPABILITIES_FOLDER):
            for fname in files:
                if not fname.endswith(".json"):
                    continue
                tool_name = os.path.splitext(fname)[0]
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r") as f:
                        tool_map[tool_name] = (json.load(f), fpath)
                except json.JSONDecodeError:
                    print(f"  ⚠ Skipping invalid JSON: {fpath}")
        return tool_map
