import chromadb

# -------- INIT CHROMA ----------
persist_directory = "./db/embedding_db"
chroma_client = chromadb.PersistentClient(path=persist_directory)
collection = chroma_client.get_or_create_collection("tool_embeddings")

print(f"ChromaDB initialized at '{persist_directory}' with collection 'tool_embeddings' containing {collection.count()} tools.")

data = collection.get()
for datum in data["documents"]:
    print(f"Tool in DB: {datum['id']} - {datum['document']}")