from typing import List, Tuple

from agent.models import ExecutionPlan, Task
from tools.db_connection import DBConnection
from tools.file_tracker import FileTracker
from .decomposer import QueryDecomposer
from .executor import TaskExecutor
from tools.ollama_wrapper import AskSession

from tools.ollama_wrapper import chat_wrapper as ollama_chat, make_serializable


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
        
    def ask_small(self, user_input: str) -> Tuple[dict, List[str]]:
        """A simpler execution pipeline without explicit decomposition.

        Steps:
        1. Send the entire user query to the model with access to tools.
        2. Model decides which tools to use and in what order.
        3. Execute tools as the model indicates and feed results back until completion.
        """
        with AskSession(user_input, model=self.model) as ask_id:

            print(f"Processing query: {user_input} (ask_id: {ask_id})")

            tasks = [Task(id=1, query=user_input, depends_on=[])]
            plan = ExecutionPlan(tasks)

            executor = TaskExecutor(model=self.model)
            final_message, tools_used = executor.execute(plan, self.db, self.tool_registry)

            return final_message, tools_used

    def run(self, user_input: str) -> Tuple[dict, List[str]]:

        with AskSession(user_input, model=self.model) as ask_id:
            print(f"Processing query: {user_input} (ask_id: {ask_id})")
            tools_used = []

            suggested_tools = self.db.route_query(user_input)

            selected_tools = []

            #TODO: Handle 1 to n tools

            if suggested_tools and suggested_tools != ["No confident match"]:
                # Load the tool doc from disk using DBConnection helper
                tool_docs = DBConnection._load_tool_docs_map()
                for tool in suggested_tools:
                    if tool in tool_docs:
                        tool_data, _ = tool_docs[suggested_tools]
                        # Ensure the tool structure is exactly what Ollama expects
                        selected_tools = [tool_data]
                    else:
                        print(f"DEBUG: Tool '{suggested_tools}' not found in registry.")

            print(f"DEBUG: Selected tools: {selected_tools[0]['function']['name']}" if selected_tools else "DEBUG: No tools selected.")

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Use tools whereever necessary."
                    ),
                },
                {"role": "user", "content": user_input},
            ]

            response = ollama_chat(
                model=self.model,
                messages=messages,
                tools=selected_tools if selected_tools else None,
                stream=False
            )

            message = response["message"]

            # Tool execution
            if "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]
                    print(f"Executing tool: {tool_name} with arguments: {arguments}")

                    try:
                        result = self.tool_registry[tool_name](**arguments)
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

                    final = ollama_chat(
                        model=self.model,
                        messages=messages,
                        stream=False
                    )

                    return final, tools_used

            return response, tools_used