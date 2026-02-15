import os

DOCUMENTS_DIR = "tools/helper/documents"

def keyword_search(query: str, source: str):
    results = []

    for filename in os.listdir(DOCUMENTS_DIR):
        if source.lower() not in filename.lower():
            continue

        with open(os.path.join(DOCUMENTS_DIR, filename), "r") as f:
            content = f.read()
            if query.lower() in content.lower():
                results.append(filename)

    return results
