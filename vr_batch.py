from tool_registry import update_tool_registry
from fetch_tool_docs import fetch_tool_docs
from embedding.embedding import compute_tool_embeddings
from agent.agent import Agent

import csv
import time
import os

if __name__ == "__main__":
    tool_registry = update_tool_registry()  # Load tools into tool registry
    tool_doc_list = fetch_tool_docs()  # Load tool documentation into a list
    tool_embedding = compute_tool_embeddings(
        tool_doc_list
    )  # Compute embeddings for the loaded tools

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