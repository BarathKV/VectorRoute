import ollama

from agent.select_tool import select_best_tool
from agent.validation import validate_and_coerce

class Agent:
    def __init__(self,tool_registry,tools_embeddings,model: str = "llama3.2:3b"):
        self.tools_embeddings = tools_embeddings
        self.tool_registry = tool_registry
        self.model = model


    def run(self,user_input: str):
        tools_used = []
        selected_tools = select_best_tool(
            user_query=user_input,
            tool_embeddings=self.tools_embeddings,
        )
        # print(f"Selected tools: {[tool['function']['name'] for tool in selected_tools]}")

        messages = [
            {
                "role": "system",
                "content": (
                    "Use tools whereever necessary."
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
                print(f"Executing tool: {tool_name} with arguments: {arguments}")

                try:
                    # validate and coerce string arguments into their
                    # proper python types (int, float, list, dict, bool)
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