from agent.base_agent import BaseAgent
import csv
import time

class BatchProcessor:
    def __init__(self, agent:BaseAgent, input_file:str, output_file:str):
        self.agent = agent
        self.input_file = input_file
        self.output_file = output_file

    def process_batch(self):
        # TODO: Implement TQDM for progress tracking and ETA estimation
        with open(self.input_file, "r", newline="") as infile, \
            open(self.output_file, "w", newline="") as outfile:

            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            # TODO: Update header to match ollama output formats
            writer.writerow(["user_query", "agent_response", "tools_used", "query_duration"])
            outfile.flush()

            for row in reader:
                original_value = row[0]
                print(f"Query: {original_value}")

                query_start_time = time.time()
                agent_response, tools_used = self.agent.run(original_value)
                query_end_time = time.time()
                query_duration = query_end_time - query_start_time
                
                writer.writerow([original_value, agent_response["message"], tools_used, query_duration])
                outfile.flush()  # ensures it is saved immediately