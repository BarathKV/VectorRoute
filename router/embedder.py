import json
import ollama

def capability_to_text(capability_path: str) -> str:
    with open(capability_path) as f:
        cap = json.load(f)

    parts = [
        f"Domain: {cap['domain']}",
        f"Description: {cap['description']}",
        "Capabilities:"
    ]

    for tool in cap["tools"]:
        parts.append(f"- {tool['purpose']}")

    parts.append("Example user queries:")
    for q in cap["example_queries"]:
        parts.append(f"- {q}")

    if "limitations" in cap:
        parts.append("Limitations:")
        for l in cap["limitations"]:
            parts.append(f"- {l}")

    return "\n".join(parts)


def embed_text(text: str) -> list[float]:
    response = ollama.embed(
        model="nomic-embed-text",
        input=text
    )
    return response["embeddings"][0]