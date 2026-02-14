import ollama

from agent.select_tool import select_best_tool

class Agent:
    def __init__(self,tool_registry,tools_embeddings,model: str = "functiongemma:latest"):
        self.tools_embeddings = tools_embeddings
        self.tool_registry = tool_registry
        self.model = model


    def run(self,user_input: str):
        selected_tools = select_best_tool(
            user_query=user_input,
            tool_embeddings=self.tools_embeddings,
        )
        # print(f"Selected tools: {[tool['function']['name'] for tool in selected_tools]}")

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

                result = self.tool_registry[tool_name](**arguments)

                messages.append(message)
                messages.append({
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": str(result),
                })

                final = ollama.chat(
                    model=self.model,
                    messages=messages,
                )

                return final["message"]["content"]

        return message["content"]