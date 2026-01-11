from router.embedder import embed_text
from router.filters import apply_filters

class MCPRouter:
    def __init__(self, index, capabilities):
        self.index = index
        self.capabilities = capabilities

    def route(self, query: str, top_k=2):
        query_embedding = embed_text(query)

        candidates = self.index.search(query_embedding, top_k=top_k)

        candidates = apply_filters(
            candidates,
            query,
            self.capabilities
        )

        return candidates
