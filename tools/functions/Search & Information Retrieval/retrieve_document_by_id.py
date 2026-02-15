import os

DOCUMENTS_DIR = "tools/helper/documents"

def retrieve_document_by_id(document_id: str):
    filepath = os.path.join(DOCUMENTS_DIR, document_id)

    if not os.path.exists(filepath):
        return None

    with open(filepath, "r") as f:
        return f.read()
