import os
import time

DOCUMENTS_DIR = "documents"

def search_recent_documents(query: str, days: int):
    results = []
    now = time.time()
    cutoff = days * 86400

    for filename in os.listdir(DOCUMENTS_DIR):
        filepath = os.path.join(DOCUMENTS_DIR, filename)
        modified_time = os.path.getmtime(filepath)

        if now - modified_time <= cutoff:
            with open(filepath, "r") as f:
                if query.lower() in f.read().lower():
                    results.append(filename)

    return results
