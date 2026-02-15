import os

DOCUMENTS_DIR = "documents"

def ranked_search(query: str, limit: int):
    scores = []

    query_terms = query.lower().split()

    for filename in os.listdir(DOCUMENTS_DIR):
        with open(os.path.join(DOCUMENTS_DIR, filename), "r") as f:
            content = f.read().lower()
            score = sum(content.count(term) for term in query_terms)

            if score > 0:
                scores.append({
                    "document": filename,
                    "score": score
                })

    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores[:limit]
