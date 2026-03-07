from tools.tool_registry import update_tool_registry
from agent.agent import Agent
# from agent.clasical_agent import ClassicalAgent
from agent.batch_processor import BatchProcessor

import os
import time

if __name__ == "__main__":
    # Load tools into tool registry
    tool_registry = update_tool_registry()

    # Vector Route Agent
    agent = Agent(tool_registry, model="functiongemma:latest")

    # Clasical Agent
    # agent = ClassicalAgent(tool_registry,tool_embedding)

    input_file = "io/queries.csv"
    input_file = os.path.abspath(input_file)

    folder = "vr" if isinstance(agent, Agent) else "clasical"

    output_file = f"io/{folder}/agent_run_log_{time.time()}.csv"
    outfile = os.path.abspath(output_file)

    bp = BatchProcessor(agent,input_file,output_file)

    bp.process_batch()