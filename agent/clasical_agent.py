import ollama
from pydantic import BaseModel

class Tool(BaseModel):
    name: str
    description: str
    parameters: dict

class ClassicalAgent:
    def __init__(self, tool_registry, tools_embeddings, model: str = "functiongemma:latest"):
        self.tools_embeddings = tools_embeddings
        self.tool_registry = tool_registry
        self.model = model

    def run(self, user_input: str) -> tuple[str, list]:
        tools_called = []
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an assistant. "
                    "Use tools only if necessary."
                ),
            },
            {"role": "user", "content": user_input},
        ]
        # print(f"Tool registry: {self.tool_registry}")

        # Convert tool_registry to a list of Tool objects
        tools = [
            Tool(
                name=name,
                description=f"Function {name} from the tool registry.",
                parameters={"type": "object", "properties": {}}
            ).dict() for name in self.tool_registry.keys()
        ]

        response = ollama.chat(
            model=self.model,
            messages=messages,
            tools=tools if tools else None,
        )

        message = response["message"]

        if "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]

                result = self.tool_registry[tool_name](**arguments)

                messages.append(message)
                tools_called.append(tool_name)
                messages.append({
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": str(result),
                })

                final = ollama.chat(
                    model=self.model,
                    messages=messages,
                    tools=tools if tools else None,
                )
                print(f"Final response after tool execution: {final['message']['content']}")
                return final["message"]["content"], tools_called

        print(f"Final response without tool execution: {message['content']}")
        return message["content"], tools_called