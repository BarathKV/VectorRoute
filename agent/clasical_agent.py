from typing import Optional, Tuple

from tools.db_connection import DBConnection
from tools.ollama_wrapper import chat_wrapper as ollama_chat


class ClassicalAgent:
    def __init__(self, tool_registry=None, tools_embeddings=None, model: str = "functiongemma:latest"):
        self.tools_embeddings = tools_embeddings
        self.tool_registry = tool_registry
        self.model = model

    def run(self, user_input: str) -> Tuple[Optional[str], list]:
        messages = []
        tools_used = []

        try:
            tool_docs = DBConnection.load_tool_context()
        except Exception:
            tool_docs = {}
        
        response = ollama_chat(
            model=self.model,
            messages=[{"role": "user", "content": user_input}],
            tools=list(tool_docs.values()) if tool_docs else None,
        )

        print(response.dict())

        message = response["message"]

        # Tool execution
        if "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tools_used.append(tool_name)
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
                )

                print(final.dict())

                return final, tools_used

        return response, tools_used