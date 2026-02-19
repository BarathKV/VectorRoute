from tool_registry import update_tool_registry
from fetch_tool_docs import fetch_tool_docs
from embedding.embedding import compute_tool_embeddings
from agent.agent import Agent


if __name__ == "__main__":
    tool_registry = update_tool_registry()  # Load tools into tool registry
    tool_doc_list = fetch_tool_docs()  # Load tool documentation into a list
    tool_embedding = compute_tool_embeddings(
        tool_doc_list
    )  # Compute embeddings for the loaded tools

    # agent = Agent(tool_registry, tool_embedding,model="llama3.2:3b")
    agent = Agent(tool_registry, tool_embedding,model="granite3.1-moe:3b")
    
    queries = [
        "What is the weather like?",
        # "What is 42 plus 11?",
        # "Explain transformers in machine learning"
    ]

    for query in queries:
        response, tools_used = agent.run(query)
        print(f"Response: {response}")
        print(f"Response Message: {response['message']['content']}")
        print(f"Tools used: {tools_used}")
