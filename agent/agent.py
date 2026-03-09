import json
import ollama
from typing import List, Tuple

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

    def multi_step_run(self, user_input: str) -> Tuple[dict, List[str]]:
        """Handle a single user message containing multiple questions.

        Steps:
        - Ask the LLM to split the input into a JSON array of questions.
        - Run each question separately via `run()`.
        - Ask the LLM to combine the individual Q/A pairs into one reply.

        Returns: (final_message, tools_used_list)
        """
        tools_used_total: List[str] = []

        # 1) Ask model to split into separate questions (expect JSON array)
        split_messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict JSON formatter. Split the following user message into "
                    "separate questions and return ONLY a JSON array of strings (no explanation)."
                ),
            },
            {"role": "user", "content": user_input},
        ]

        try:
            split_resp = ollama.chat(model=self.model, messages=split_messages)
            split_msg = split_resp.get("message", {})
            split_text = ""
            if isinstance(split_msg, dict):
                split_text = split_msg.get("content") or split_msg.get("text") or str(split_msg)
            else:
                split_text = str(split_msg)

            # Extract JSON array from potential surrounding text
            start = split_text.find("[")
            end = split_text.rfind("]")
            if start != -1 and end != -1:
                json_text = split_text[start : end + 1]
                queries = json.loads(json_text)
                if not isinstance(queries, list):
                    queries = [user_input]
            else:
                queries = [user_input]
        except Exception:
            queries = [user_input]

        # 2) Run each query separately
        qa_pairs = []
        for q in queries:
            resp, tools_used = self.run(q)
            tools_used_total.extend(tools_used)

            if isinstance(resp, dict):
                answer_text = resp.get("content") or resp.get("text") or str(resp)
            else:
                answer_text = str(resp)

            qa_pairs.append({"question": q, "answer": answer_text})

        # 3) Ask the model to combine the individual answers into one coherent reply
        combine_messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Combine the following question/answer pairs "
                    "into a single, user-facing response. Keep it clear and concise."
                ),
            },
            {"role": "user", "content": json.dumps({"original": user_input, "qa_pairs": qa_pairs}, indent=2)},
        ]

        combined_resp = ollama.chat(model=self.model, messages=combine_messages)
        final_message = combined_resp.get("message", {})

        return final_message, tools_used_total


        