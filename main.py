from tool_registry import update_tool_registry
from fetch_tool_docs import fetch_tool_docs
from embedding.tool_embedder import compute_tool_embeddings
from agent.agent import Agent


if __name__ == "__main__":
    tool_registry = update_tool_registry()  # Load tools into tool registry
    tool_doc_list = fetch_tool_docs()  # Load tool documentation into a list
    tool_embedding = compute_tool_embeddings(
        tool_doc_list
    )  # Compute embeddings for the loaded tools

    agent = Agent(tool_registry, tool_embedding)
    
    queries = [
        "calculcate my bmi, i am 170 cm in height and 60 kg in weight",
        "What is the current price of Apple stock?",
        "Convert 16 inches to feet"
    ]

    for query in queries:
        response, tools_used = agent.run(query)
        print(f"Response: {response}")
        print(f"Response Message: {response['message']['content']}")
        print(f"Tools used: {tools_used}")
