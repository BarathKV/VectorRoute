from typing import Dict, List, Optional, Any

import ollama

from tools.db_connection import DBConnection
from tools.ollama_wrapper import chat_wrapper as ollama_chat
from .validation import validate_and_coerce


class Task:
    def __init__(self, id: int, query: str, depends_on: Optional[List[int]] = None):
        self.id = id
        self.query = query
        self.depends_on = depends_on or []
        self.result: Any = None
        self.status: str = "pending"  # pending, in-progress, completed, failed
        self.message: List[dict] = [
            {
                "role": "system",
                "content": """You are a helpful assistant with access to tools.
                Follow instructions and use tools when appropriate.""",
            },
            {"role": "user", "content": self.query},
        ]  # to store the message history of the task for better context management
        self.tools_used: List[str] = []  # to track which tools were used during execution
    
    def write_message_to_file(self):
        import json
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"io/task_msg_jsons/task_message_{timestamp}.json"
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
        serializable_message = make_serializable(self.message)
        with open(filename, "w") as f:
            json.dump(serializable_message, f, indent=2)
        print(f"DEBUG: Message dumped to {filename}")

    def run(self,db:DBConnection,model:str,tool_registry:Dict[str, callable]) -> bool:
        """Execute the task by routing the query, selecting tools, and interacting with the LLM."""
        try:
            # Corrected route_query call
            suggested_tools = db.route_query(self.query)

            # Try to locate the capability JSON for the selected tool
            selected_tools = []
            if suggested_tools and suggested_tools != "No confident match":
                # Load the tool doc from disk using DBConnection helper
                tool_docs = DBConnection._load_tool_docs_map()
                if suggested_tools in tool_docs:
                    tool_data, _ = tool_docs[suggested_tools]
                    # Ensure the tool structure is exactly what Ollama expects
                    selected_tools = [tool_data]
                else:
                    print(f"DEBUG: Tool '{suggested_tools}' not found in registry.")

            print(f"DEBUG: Selected tools: {selected_tools[0]['function']['name']}" if selected_tools else "DEBUG: No tools selected.")

            response = ollama_chat(
                model=model,
                messages=self.message,
                tools=selected_tools if selected_tools else None,
            )

            current_message = response["message"]

            self.message.append(current_message)

            # Tool execution
            if "tool_calls" in current_message:
                for tool_call in current_message["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]

                    try:
                        print(f"DEBUG: Executing tool: {tool_name} with arguments: {arguments}")
                        validated_args = validate_and_coerce(
                            arguments, tool_registry[tool_name]
                        )
                        print(f"DEBUG: Validated arguments: {validated_args}")

                        result = tool_registry[tool_name](**validated_args)

                        print(f"Tool result: {result}")

                        self.message.append(current_message)
                        self.tools_used.append(tool_name)
                        self.message.append(
                            {
                                "role": "tool",
                                "tool_name": tool_name,
                                "content": str(result),
                            }
                        )

                        final = ollama_chat(
                            model=model,
                            messages=self.message,
                        )

                        self.message.append(final["message"])
                        self.result = final["message"]

                    except ValueError as error:
                        error_message = f"VALIDATION_ERROR:{error}"
                        print(f"DEBUG: Validation error: {error}")
                        return error_message, self.tools_used

                    except TypeError as error:
                        error_message = f"TYPE_ERROR:{error}"
                        print(f"DEBUG: Type error: {error}")
                        return error_message, self.tools_used

                    except Exception as error:
                        error_message = f"RUNTIME_ERROR:{error}"
                        print(f"DEBUG: Runtime error: {error}")
                        return error_message, self.tools_used

            # Write the context of the task in a file before returning answer
            self.write_message_to_file()

            return True
        except Exception as e:
            print(f"DEBUG: Unexpected error in run(): {e}")
            return False

    def get_context(self) -> List[dict]:
        """Return the entire context of the task, including messages."""
        return self.message

    def get_result(self) -> Optional[str]:
        """Return only the final LLM answer after the task is executed."""
        return self.result


class ExecutionPlan:
    def __init__(self, tasks: List[Task]):
        self.tasks = tasks

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def is_complete(self) -> bool:
        return all(task.status == "completed" for task in self.tasks)
