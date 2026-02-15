import os
import time

DOCUMENTS_DIR = "documents"

def search_metadata(metadata_field: str, value: str):
    results = []

    for filename in os.listdir(DOCUMENTS_DIR):
        filepath = os.path.join(DOCUMENTS_DIR, filename)
        stats = os.stat(filepath)

        metadata = {
            "filename": filename,
            "size": str(stats.st_size),
            "modified": time.ctime(stats.st_mtime)
        }

        if metadata_field in metadata and value.lower() in metadata[metadata_field].lower():
            results.append(metadata)

    return results
