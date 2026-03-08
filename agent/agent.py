import ollama

from tools.db_connection import DBConnection
from tools.file_tracker import FileTracker


class Agent:
    """Agent that wires the FileTracker and Chroma DB together.

    Responsibilities:
    - initialize model, FileTracker and DBConnection
    - run the tracker, obtain added/modified/deleted tools
    - sync ChromaDB accordingly via DBConnection
    """

    def __init__(self, model: str = "llama3.2:3b", db: DBConnection = None, tracker: FileTracker = None):
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

    def run(self, user_input: str):
        """Route a user query to the best-matching tool via ChromaDB.

        Returns: (best_tool_name, tools_used_list)
        """
        tools_used = []

        # Use DBConnection.route_query to pick the best tool name
        best_tool_name = self.db.route_query(user_input)

        # Try to locate the capability JSON for the selected tool
        selected_tools = None
        if best_tool_name and best_tool_name != "No confident match":
            for t in self.tools_embeddings:
                func = t.get("function", {})
                if func.get("name") == best_tool_name:
                    selected_tools = [t]
                    break

        messages = [
            {
                "role": "system",
                "content": "Use tools whereever necessary.",
            },
            {"role": "user", "content": user_input},
        ]

        response = ollama.chat(
            model=self.model,
            messages=messages,
            tools=selected_tools if selected_tools else None,
        )

        message = response["message"]

        # Tool execution
        if "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]
                print(f"Executing tool: {tool_name} with arguments: {arguments}")

                try:
                    validated_args = validate_and_coerce(arguments, self.tool_registry[tool_name])
                    print(f"Validated arguments: {validated_args}")
                    result = self.tool_registry[tool_name](**validated_args)
                except ValueError as error:
                    error_message = f"VALIDATION_ERROR:{error}"
                    return error_message, tools_used
                except TypeError as error:
                    error_message = f"ERROR:{error}"
                    return error_message, tools_used

                messages.append(message)
                tools_used.append(tool_name)
                messages.append({
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": str(result),
                })

                final = ollama.chat(
                    model=self.model,
                    messages=messages,
                )

                return final["message"], tools_used

        return response["message"], tools_used