from typing import List, Tuple

from tools.db_connection import DBConnection
from tools.file_tracker import FileTracker
from .decomposer import QueryDecomposer
from .executor import TaskExecutor
from tools.ollama_wrapper import AskSession


class Agent:
    """Agent that wires the FileTracker and Chroma DB together.

    Responsibilities:
    - initialize model, FileTracker and DBConnection
    - run the tracker, obtain added/modified/deleted tools
    - sync ChromaDB accordingly via DBConnection
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        db: DBConnection = None,
        tracker: FileTracker = None,
    ):
        self.model = model
        
        # instantiate or use provided FileTracker
        self.tracker = tracker or FileTracker()

        # instantiate or use provided DBConnection
        self.db = db or DBConnection()

        # Run tracker and sync DB on initialization
        changes = self.tracker.get_file_changes()
        self.db.update_db(changes=changes)

        # build runtime tool registry (callable functions)
        self.tool_registry = self.tracker.get_tool_registry()

        print(
            f"\n\n\nAgent initialized with model {self.model}. Tool registry: {len(self.tool_registry.keys())}"
        )

    def ask(self, user_input: str) -> Tuple[dict, List[str]]:
        """A more advanced execution pipeline using query decomposition.

        Steps:
        1. Decomposed to atomic tasks with potential dependencies.
        2. Execute each task sequentially while resolving dependencies.
        3. Aggregate all task results into a single final response.
        """
        with AskSession(user_input, model=self.model) as ask_id:
            # Initialize decomposer and executor
            decomposer = QueryDecomposer(model=self.model)
            executor = TaskExecutor(model=self.model)

            messages = [{"role": "user", "content": user_input}]

            # 1. Decompose
            print(f"Decomposing query: {user_input} (ask_id: {ask_id})")
            plan = decomposer.decompose(user_input, messages=messages)

            # 2. Execute & 3. Aggregate
            final_message, tools_used = executor.execute(plan, self.db, self.tool_registry)

            return final_message, tools_used
