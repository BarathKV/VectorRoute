from typing import Optional, Tuple

from .models import Task
from tools.file_tracker import FileTracker
from tools.db_connection import DBConnection


class ClassicalAgent:
    def __init__(self, tool_registry=None, tools_embeddings=None, model: str = "functiongemma:latest"):
        self.tools_embeddings = tools_embeddings
        self.tool_registry = tool_registry
        self.model = model

    def run(self, user_input: str, db: Optional[DBConnection] = None) -> Tuple[Optional[str], list]:
        """Create a Task and delegate execution to `Task.run()`.

        - Uses `FileTracker.get_tool_registry()` to build the tool registry.
        - If `db` is not provided, a default `DBConnection()` will be created.
        Returns a tuple: (final_result_or_error, tools_used_list)
        """
        # Ensure we have a DB connection
        if db is None:
            try:
                db = DBConnection()
            except Exception:
                db = None

        # Build tool registry from files on disk (preferred)
        try:
            tool_registry = FileTracker.get_tool_registry()
        except Exception:
            # Fallback to any provided registry
            tool_registry = self.tool_registry or {}

        task = Task(id=0, query=user_input)

        result = task.run(db, self.model, tool_registry)

        # `Task.run` may return True on success, or (error_message, tools_used) on failures
        if isinstance(result, tuple) and len(result) == 2:
            return result[0], result[1]

        if result is True:
            final = task.get_result()
            return final, task.tools_used

        # result was False or unexpected
        return None, task.tools_used