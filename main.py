from model.embedding import get_embedding
from similarity.cosine import cosine_similarity
from tools.tool_registry import TOOL_REGISTRY

import os
import json
import ollama

def main():
    def build_tool_embeddings(tools):
        tool_embeddings = []

        for tool in tools:
            fn = tool["function"]
            text = f"{fn['name']}: {fn['description']}"
            embedding = get_embedding(text)

            tool_embeddings.append({
                "tool": tool,
                "name": fn["name"],
                "embedding": embedding,
            })

        return tool_embeddings
    
    TOOLS = []
    tools_folder = os.path.join(os.path.dirname(__file__), "tools")

    for root, _, files in os.walk(tools_folder):
        for file in files:
            if file == "capability.json":
                with open(os.path.join(root, file), "r") as f:
                    try:
                        tool_data = json.load(f)
                        TOOLS.append(tool_data)
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON in file: {os.path.join(root, file)}")
    
    TOOL_EMBEDDINGS = build_tool_embeddings(TOOLS)

    def select_best_tool(user_query: str, tool_embeddings, threshold: float = 0.2):
        query_embedding = get_embedding(user_query)

        best_score = -1
        best_tool = None

        for item in tool_embeddings:
            score = cosine_similarity(query_embedding, item["embedding"])

            if score > best_score:
                best_score = score
                best_tool = item["tool"]

        if best_score < threshold:
            return []  # No tool passed to LLM

        return [best_tool]

    def run_agent(user_input: str, model: str = "functiongemma:latest"):
        selected_tools = select_best_tool(
            user_query=user_input,
            tool_embeddings=TOOL_EMBEDDINGS,
        )

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
            model=model,
            messages=messages,
            tools=selected_tools if selected_tools else None,
        )

        message = response["message"]

        # Tool execution
        if "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]

                result = TOOL_REGISTRY[tool_name](**arguments)

                messages.append(message)
                messages.append({
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": str(result),
                })

                final = ollama.chat(
                    model=model,
                    messages=messages,
                )

                return final["message"]["content"]

        return message["content"]

    print(run_agent("What is the weather like in Tokyo?"))
    print(run_agent("What is 42 plus 11?"))
    print(run_agent("Explain transformers in machine learning"))



if __name__ == "__main__":
    main()
