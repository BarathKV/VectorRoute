import sys
import chromadb

# -------- INIT CHROMA ----------
persist_directory = "./embedding_db"

try:
    chroma_client = chromadb.PersistentClient(path=persist_directory)
except Exception as e:
    print(f"Failed to initialize Chroma client at '{persist_directory}': {e}")
    sys.exit(1)

try:
    collection = chroma_client.get_collection("tool_embeddings")
except Exception:
    # Fallback to create if it doesn't exist
    collection = chroma_client.get_or_create_collection("tool_embeddings")

print(
    f"ChromaDB initialized at '{persist_directory}' with collection 'tool_embeddings' containing {collection.count()} data points."
)

# Retrieve all data points from the collection including embeddings
results = collection.get(include=["documents", "metadatas", "embeddings"])
ids = results.get("ids", [])
documents = results.get("documents", [])
metadatas = results.get("metadatas", [])
embeddings = results.get("embeddings", [])

print(f"Retrieved {len(ids)} documents from ChromaDB")
for i, doc_id in enumerate(ids):
    document = documents[i] if i < len(documents) else None
    metadata = metadatas[i] if i < len(metadatas) else None
    embedding = embeddings[i] if i < len(embeddings) else None
    print(f"\n[{i+1}] ID: {doc_id}")
    print(f"    Document: {document}")
    print(f"    Metadata: {metadata}")
    if embedding is None:
        print("    Embedding: None")
    else:
        # Print small preview for readability (show length and first values)
        try:
            emb_len = len(embedding)
            emb_preview = embedding[:16] if emb_len > 16 else embedding
            print(f"    Embedding (len={emb_len}): {emb_preview} ...")
        except Exception:
            # Fallback if embedding is not a sequence
            print(f"    Embedding: {embedding}")