from tools.tool_registry import update_tool_registry
from tools.fetch_tool_docs import fetch_tool_docs
from embedding.tool_embedder import compute_tool_embeddings
from tools.file_tracker import FileChangeTracker
from agent.agent import Agent
# from agent.clasical_agent import ClassicalAgent
from agent.batch_processor import BatchProcessor

import os
import time

def main(argc, argv):
    print("Starting the tool embedding and agent processing pipeline...")
    


if __name__ == "__main__":
    main(len(os.sys.argv), os.sys.argv)
    # Initialize file change tracker
    tracker = FileChangeTracker()
    changed_tools = tracker.get_changed_tools()
    
    if changed_tools:
        print(f"\nDetected {len(changed_tools)} tools with changes:")
        for tool_name in sorted(changed_tools):
            print(f"  - {tool_name}")
    else:
        print("\nNo changes detected. Using cached embeddings.")
    
    # Load tools into tool registry
    tool_registry = update_tool_registry()
    
    # Load tool documentation into a list
    tool_doc_list = fetch_tool_docs()
    
    # Compute embeddings (incremental mode)
    tool_embedding = compute_tool_embeddings(
        tool_doc_list,
        changed_tools=changed_tools
    )
    
    # Mark files as processed
    tracker.mark_as_processed()

    # Vector Route Agent
    agent = Agent(tool_registry, tool_embedding, model="functiongemma:latest")

    # Clasical Agent
    # agent = ClassicalAgent(tool_registry,tool_embedding)

    input_file = "io/queries.csv"
    input_file = os.path.abspath(input_file)

    folder = "vr" if isinstance(agent, Agent) else "clasical"

    output_file = f"io/{folder}/agent_run_log_{time.time()}.csv"
    outfile = os.path.abspath(output_file)

    bp = BatchProcessor(agent,input_file,output_file)

    bp.process_batch()