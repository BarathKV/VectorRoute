from tool_utils.tool_registry import update_tool_registry
from tool_utils.fetch_tool_docs import fetch_tool_docs
from tool_utils.file_tracker import FileChangeTracker
from embedding.tool_embedder import compute_tool_embeddings
from agent.agent import Agent

import csv
import time
import os

if __name__ == "__main__":
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

    agent = Agent(tool_registry, tool_embedding)

    input_file = "io/queries.csv"
    input_file = os.path.abspath(input_file)
    output_file = f"io/vr/agent_run_log_{time.time()}.csv"
    outfile = os.path.abspath(output_file)

    with open(input_file, "r", newline="") as infile, \
        open(output_file, "w", newline="") as outfile:

        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        # Write new header
        writer.writerow(["user_query", "agent_response", "tools_used", "query_duration"])
        outfile.flush()

        for row in reader:
            original_value = row[0]
            print(f"Query: {original_value}")

            query_start_time = time.time()
            agent_response, tools_used = agent.run(original_value)
            query_end_time = time.time()
            query_duration = query_end_time - query_start_time
            

            writer.writerow([original_value, agent_response, tools_used, query_duration])
            outfile.flush()  # ensures it is saved immediately