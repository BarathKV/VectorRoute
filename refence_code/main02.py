def get_weather(city: str) -> str:
    return f"The weather in {city} is sunny and 25°C."


def add_numbers(a: int, b: int) -> int:
    return a + b

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_numbers",
            "description": "Add two numbers together",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"]
            }
        }
    }
]

TOOL_REGISTRY = {
    "get_weather": get_weather,
    "add_numbers": add_numbers,
}

import ollama
import math

def cosine_similarity(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    return dot / (norm1 * norm2)

def get_embedding(text: str, model: str = "nomic-embed-text"):
    response = ollama.embeddings(
        model=model,
        prompt=text
    )
    return response["embedding"]

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
    print(f"LLM Response: {message}")

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
            print(len(messages))

            final = ollama.chat(
                model=model,
                messages=messages,
            )

            return final["message"]["content"]

    return message["content"]

# print(run_agent("What is the weather like in Tokyo?"))
print(run_agent("What is 42 plus 11?"))
# print(run_agent("Explain transformers in machine learning"))
