import faiss
import numpy as np

class ServerIndex:
    def __init__(self, dim: int):
        self.index = faiss.IndexFlatL2(dim)
        self.server_ids = []

    def add(self, server_id: str, embedding: list[float]):
        vec = np.array([embedding]).astype("float32")
        self.index.add(vec)
        self.server_ids.append(server_id)

    def search(self, query_embedding: list[float], top_k=3):
        q = np.array([query_embedding]).astype("float32")
        distances, indices = self.index.search(q, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            results.append({
                "server_id": self.server_ids[idx],
                "score": float(1 / (1 + dist))
            })
        return results