import os

DOCUMENTS_DIR = "tools/helper/documents"

def search_documents_by_title(title_query: str):
    matches = []

    for filename in os.listdir(DOCUMENTS_DIR):
        if title_query.lower() in filename.lower():
            matches.append(filename)

    return matches
