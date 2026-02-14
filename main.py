from tools.tool_registry import update_tool_registry
from tools.fetch_tool_docs import fetch_tool_docs
from embedding.embedding import compute_tool_embeddings
from agent.agent import Agent


if __name__ == "__main__":
    tool_registry = update_tool_registry()  # Load tools into tool registry
    tool_doc_list = fetch_tool_docs()  # Load tool documentation into a list
    tool_embedding = compute_tool_embeddings(
        tool_doc_list
    )  # Compute embeddings for the loaded tools

    agent = Agent(tool_registry, tool_embedding)
    print(agent.run("What is the weather like in Tokyo?"))
    print(agent.run("What is 42 plus 11?"))
    print(agent.run("Explain transformers in machine learning"))
