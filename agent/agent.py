import json
import ollama
from typing import List, Tuple

from tools.db_connection import DBConnection
from tools.file_tracker import FileTracker
from .validation import validate_and_coerce
from .decomposer import QueryDecomposer
from .executor import TaskExecutor


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

    def run(self, user_input: str):
        """Route a user query to the best-matching tool via ChromaDB.

        Returns: (best_tool_name, tools_used_list)
        """
        tools_used = []

        # Use DBConnection.route_query to pick the best tool name
        best_tool_name = self.db.route_query(user_input)

        # Try to locate the capability JSON for the selected tool
        selected_tools = []
        if best_tool_name and best_tool_name != "No confident match":
            # Load the tool doc from disk using DBConnection helper
            tool_docs = self.db._load_tool_docs_map()
            if best_tool_name in tool_docs:
                tool_data, _ = tool_docs[best_tool_name]
                # Ensure the tool structure is exactly what Ollama expects
                selected_tools = [tool_data]
            else:
                print(f"DEBUG: Tool '{best_tool_name}' not found in registry.")

        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant with access to tools. Follow instructions and use tools when appropriate.",
            },
            {"role": "user", "content": user_input},
        ]

        print(f"DEBUG: Selected tools: {selected_tools[0]['function']['name']}")

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
                # print(f"Executing tool: {tool_name} with arguments: {arguments}")

                try:
                    print(f"DEBUG: Executing tool: {tool_name} with arguments: {arguments}")
                    validated_args = validate_and_coerce(
                        arguments, self.tool_registry[tool_name]
                    )
                    print(f"DEBUG: Validated arguments: {validated_args}")
                    result = self.tool_registry[tool_name](**validated_args)
                    print(f"Tool result: {result}")
                except ValueError as error:
                    error_message = f"VALIDATION_ERROR:{error}"
                    print(f"DEBUG: Validation error: {error}")
                    return error_message, tools_used
                except TypeError as error:
                    error_message = f"TYPE_ERROR:{error}"
                    print(f"DEBUG: Type error: {error}")
                    return error_message, tools_used
                except Exception as error:
                    error_message = f"RUNTIME_ERROR:{error}"
                    print(f"DEBUG: Runtime error: {error}")
                    return error_message, tools_used

                messages.append(message)
                tools_used.append(tool_name)
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": str(result),
                    }
                )

                import json
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"agent_message_{timestamp}.json"
                # Convert message to a serializable dict if needed
                def make_serializable(obj):
                    if isinstance(obj, dict):
                        return {k: make_serializable(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [make_serializable(i) for i in obj]
                    elif hasattr(obj, "__dict__"):
                        return make_serializable(vars(obj))
                    else:
                        try:
                            json.dumps(obj)
                            return obj
                        except TypeError:
                            return str(obj)
                serializable_message = make_serializable(messages)
                with open(filename, "w") as f:
                    json.dump(serializable_message, f, indent=2)
                print(f"DEBUG: Message dumped to {filename}")

                final = ollama.chat(
                    model=self.model,
                    messages=messages,
                )

                return final["message"], tools_used

        return response["message"], tools_used

    def run_better(self, user_input: str) -> Tuple[dict, List[str]]:
        """A more advanced execution pipeline using query decomposition.

        Steps:
        1. Decompose the user query into atomic tasks with potential dependencies.
        2. Execute each task sequentially while resolving dependencies.
        3. Aggregate all task results into a single final response.
        """
        # Initialize decomposer and executor
        decomposer = QueryDecomposer(model=self.model)
        executor = TaskExecutor(agent=self, model=self.model)

        # 1. Decompose
        print(f"Decomposing query: {user_input}")
        plan = decomposer.decompose(user_input)

        # 2. Execute & 3. Aggregate
        final_message, tools_used = executor.execute(plan)

        return final_message, tools_used
