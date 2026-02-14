from model.embedding import get_embedding
from similarity.cosine import cosine_similarity

def select_best_tool(user_query: str, tool_embeddings, threshold: float = 0.2):
    query_embedding = get_embedding(user_query)

    best_score = -1
    best_tool = None

    for item in tool_embeddings:
        score = cosine_similarity(query_embedding, item["embedding"])
        # print(f"Tool: {item['name']}, Similarity Score: {score:.4f}")

        if score > best_score:
            best_score = score
            best_tool = item["tool"]

    if best_score < threshold:
        return []  # No tool passed to LLM

    return [best_tool]