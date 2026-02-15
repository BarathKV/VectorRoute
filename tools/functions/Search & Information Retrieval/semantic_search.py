import os

DOCUMENTS_DIR = "documents"

def semantic_search(query: str, corpus: str):
    matches = []

    query_words = set(query.lower().split())

    for filename in os.listdir(DOCUMENTS_DIR):
        with open(os.path.join(DOCUMENTS_DIR, filename), "r") as f:
            content_words = set(f.read().lower().split())
            overlap = query_words.intersection(content_words)

            if overlap:
                matches.append({
                    "document": filename,
                    "matched_terms": list(overlap)
                })

    return matches
