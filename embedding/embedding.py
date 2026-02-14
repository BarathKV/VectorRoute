from model.embedding import get_embedding


def compute_tool_embeddings(tools: list) -> list:
    TOOL_EMBEDDINGS = []

    for tool in tools:
        print(f"Computing embedding for tool: {tool['function']['name']}")
        fn = tool["function"]
        text = f"{fn['name']}: {fn['description']}"
        embedding = get_embedding(text)
        print(f"Embedding computed for tool: {fn['name']}")

        TOOL_EMBEDDINGS.append(
            {
                "tool": tool,
                "name": fn["name"],
                "embedding": embedding,
            }
        )
    return TOOL_EMBEDDINGS
