from router.embedder import capability_to_text, embed_text
from router.index import ServerIndex
from router.router import MCPRouter
import json
import glob

# Load capabilities
capabilities = {}
index = None

cap_files = glob.glob("mcp_servers/**/capability.json", recursive=True)
print(cap_files)

for i, path in enumerate(cap_files):
    text = capability_to_text(path)
    emb = embed_text(text)

    if index is None:
        index = ServerIndex(len(emb))

    with open(path) as f:
        cap = json.load(f)

    server_id = cap["server_id"]
    capabilities[server_id] = cap
    index.add(server_id, emb)

router = MCPRouter(index, capabilities)

# User query
queries = ["is it raining in london?",
        "what is the price of microsoft?",
        "how is the weather at chennai today?",
        "how much did apple loose today?",
        ]

for query in queries:
    servers = router.route(query)
    print("Selected servers:", servers)