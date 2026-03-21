import os
import json
import uuid
import chromadb
from collections import Counter
from typing import Optional, Dict, Tuple

from embedding.embedder import get_embedding
from tools.file_tracker import FileTracker


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DB_PATH = os.path.join(BASE_DIR, "embedding_db")
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
        # capabilities folder path for loading docs
        self.capabilities_folder = os.path.join(
            BASE_DIR, "VectorRoute-Tools", "capabilities"
        )

    # ── Private helpers ──────────────────────────────────────────────────

    # def _build_document(self, tool_data: dict) -> str:
    #     """
    #     Turn a capability JSON dict into the text that will be embedded.
    #     Uses the function name + description + parameter descriptions.
    #     """
    #     func = tool_data.get("function", {})
    #     parts = [
    #         func.get("name", ""),
    #         func.get("description", ""),
    #     ]
    #     params = func.get("parameters", {}).get("properties", {})
    #     for param_name, param_info in params.items():
    #         parts.append(f"{param_name}: {param_info.get('description', '')}")
    #     return " | ".join(parts)

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

        def add_embedding(category: str, embedding_input: str):
            embedding = get_embedding(embedding_input)
            if not embedding:
                print(
                    f"[!] Skipping {category} for tool '{tool_name}' due to missing embedding."
                )
                return False
            print(
                f"  [+] Adding embedding for tool '{tool_name}' - category: {category}"
            )
            # Use a stable id for fixed categories (desc/long_desc/domain),
            # but generate a unique id per example query so multiple examples
            # for the same tool are stored instead of clobbering one id.
            if category == "example_query":
                id_val = f"{tool_name}_{category}_{str(uuid.uuid4())}"
            else:
                id_val = f"{tool_name}_{category}"

            self.collection.add(
                ids=[id_val],
                embeddings=[embedding],
                metadatas=[{"tool": tool_name, "category": category}],
            )
            return True

        # Example queries – each gets a unique id
        for example in examples:
            if not add_embedding("example_query", example):
                continue

        # Short description
        add_embedding("desc", description)

        # Long description
        add_embedding("long_desc", long_description)

        # Domain
        add_embedding("domain", domain)

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

    def update_db(self, changes: Optional[dict] = None) -> None:
        """
        Synchronise ChromaDB with the capability JSON files on disk.

        1. Call *get_file_changes()* to find added / modified / deleted tools.
        2. For each added tool   → _add_tool()   + update hash in SQLite.
        3. For each modified tool → _update_tool() + update hash in SQLite.
        4. For each deleted tool  → _delete_tool() (hash row stays or can be
           pruned separately).
        """
        # Accept externally computed changes (e.g. from a FileTracker) or
        # compute them here using FileTracker.
        # TODO: consider moving the FileTracker logic fully outside of this class so that DBConnection is only responsible for DB interactions and not file system tracking.
        if changes is None:
            ft = FileTracker()
            changes = ft.get_file_changes()

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
                # Persist file hash via FileTracker
                # TODO: consider decoupling the file hash tracking from the DBConnection class, as it currently has responsibilities both for managing the ChromaDB collection and for tracking file changes via FileTracker. This could lead to a cleaner separation of concerns if the file tracking logic is handled entirely outside of DBConnection, allowing DBConnection to focus solely on database interactions.
                ft = FileTracker()
                ft.update_hash_of_file(tool_name, file_path, "json")

        for tool_name in modified:
            if tool_name in tool_docs:
                tool_data, file_path = tool_docs[tool_name]
                self._update_tool(tool_name, tool_data)
                # TODO: consider decoupling the file hash tracking from the DBConnection class, as it currently has responsibilities both for managing the ChromaDB collection and for tracking file changes via FileTracker. This could lead to a cleaner separation of concerns if the file tracking logic is handled entirely outside of DBConnection, allowing DBConnection to focus solely on database interactions.
                ft = FileTracker()
                ft.update_hash_of_file(tool_name, file_path, "json")

        for tool_name in deleted:
            self._delete_tool(tool_name)
            # Also remove hashes recorded for this tool
            # TODO: consider decoupling the file hash tracking from the DBConnection class, as it currently has responsibilities both for managing the ChromaDB collection and for tracking file changes via FileTracker. This could lead to a cleaner separation of concerns if the file tracking logic is handled entirely outside of DBConnection, allowing DBConnection to focus solely on database interactions.
            ft = FileTracker()
            ft.delete_hash(tool_name, "json")
            ft.delete_hash(tool_name, "py")

        print(
            f"Sync complete  ➜  added={len(added)}  "
            f"modified={len(modified)}  deleted={len(deleted)}"
        )

    def get_top_k_counter_eg_query(
        self,
        user_query: str,
        top_k: int = 10,
        use_threshold: bool = False,
        threshold: float = 0.5,
    ) -> list[tuple[str, int]]:
        """
        Query the ChromaDB collection for the most similar example user queries.

        Returns a list of matching tool names based on the example queries.
        """
        user_embedding = get_embedding(user_query)

        results = self.collection.query(
            query_embeddings=[user_embedding],
            n_results=top_k,
            where={"category": "example_query"},
        )

        tools_found = []
        if use_threshold:
            for i, m in enumerate(results["metadatas"][0]):
                tool = m["tool"]
                dist = results["distances"][0][i]
                print(f"\n\nDEBUG: Ex-query match - tool: {tool}, dist: {dist}, sim: {1-dist}")
                if 1 - dist > threshold:
                    tools_found.append(tool)
            return tools_found
        else:
            for m in results["metadatas"][0]:
                tool = m["tool"]
                tools_found.append(tool)

        return Counter(tools_found).most_common()
    
    #TODO: may be write fucntion which checks if the other capability document details fall within a certain similarity or not

    #TODO: move route query to agent class
    def route_query(
        self,
        user_query: str,
        top_k: int = 14,
        threshold: float = 0.5,
        min_example_hits: int = 3,
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

        tools_found = []
        for i, m in enumerate(results["metadatas"][0]):
            tool = m["tool"]
            dist = results["distances"][0][i]
            # print(f"\n\nDEBUG: Ex-query match - tool: {tool}, dist: {dist}, sim: {1-dist}")
            if 1 - dist > threshold:
                tools_found.append(tool)
        count = Counter(tools_found).most_common()  # tool_name -> count of example-query matches
        print(f"Tool counts from example-query search: {dict(count)}")

        for tool_name, c in dict(count).items():
            if c >= min_example_hits:
                return tool_name
        return "No confident match"

        # tools_found = [m["tool"] for m in results["metadatas"][0]]
        # # print(f"Tools found in example-query search: {list(tools_found)}")

        # # ── Step 2: find tool with enough example matches ────────────
        # for tool_name, c in count.items():
        #     if c >= min_example_hits:

        #         # ── Step 3: validate against other categories ────────
        #         validation = self.collection.query(
        #             query_embeddings=[user_embedding],
        #             n_results=30,
        #             where={
        #                 "$and": [
        #                     {"tool": tool_name},
        #                     {
        #                         "category": {
        #                             "$in": [
        #                                 "description",
        #                                 "long_description",
        #                                 "domain",
        #                             ]
        #                         }
        #                     },
        #                 ]
        #             },
        #         )

        #         print(f"\n\nValidation results : {validation}")

        #         distances = validation["distances"][0]

        #         for d in distances:
        #             print(f"\n\nDEBUG: Validation distance for {tool_name}: {1-d}")

        #         if all(1 - d > threshold for d in distances):
        #             return tool_name

        # return "No confident match"

    # ── Helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _load_tool_docs_map() -> dict:
        """
        Walk the capabilities folder and return a dict:
        { tool_name: (filtered_json, file_path) }
        excluding 'example_user_queries'.
        """
        tool_map: dict = {}
        # Ensure BASE_DIR is defined or accessible in your scope
        caps_folder = os.path.join(BASE_DIR, "VectorRoute-Tools", "capabilities")

        for root, _, files in os.walk(caps_folder):
            for fname in files:
                if not fname.endswith(".json"):
                    continue
                tool_name = os.path.splitext(fname)[0]
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r") as f:

                        content = json.load(f)

                        # # Remove 'example_user_queries' from the loaded content
                        # content["function"].pop("example_user_queries", None)

                        tool_map[tool_name] = (content, fpath)

                except json.JSONDecodeError:
                    print(f"  ⚠ Skipping invalid JSON: {fpath}")
                except Exception as e:
                    print(f"  ⚠ Error processing {fpath}: {e}")

        return tool_map
