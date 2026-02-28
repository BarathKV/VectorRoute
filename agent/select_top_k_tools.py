from embedding.embedder import get_embedding
from embedding.similarity.cosine import cosine_similarity

def select_top_k_tools(user_query: str, tool_embeddings, k: int = 3, threshold: float = 0.2) -> list[str]:
    query_embedding = get_embedding(user_query)

    scored_tools = []
    for item in tool_embeddings:
        score = cosine_similarity(query_embedding, item["embedding"])
        scored_tools.append((item["tool"], score))

    # Sort tools by similarity score in descending order
    scored_tools.sort(key=lambda x: x[1], reverse=True)

    # Filter tools based on the threshold and select top k
    selected_tools = [tool for tool, score in scored_tools if score >= threshold][:k]

    return selected_tools