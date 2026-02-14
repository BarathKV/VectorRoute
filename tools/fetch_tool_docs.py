import os
import json


def fetch_tool_docs() -> list:
    TOOLS = []
    tools_folder = os.path.join(os.path.dirname(__file__), "capabilities")

    for root, _, files in os.walk(tools_folder):
        for file in files:
            if file.endswith(".json"):
                with open(os.path.join(root, file), "r") as f:
                    try:
                        tool_data = json.load(f)
                        TOOLS.append(tool_data)
                    except json.JSONDecodeError:
                        print(
                            f"Error decoding JSON in file: {os.path.join(root, file)}"
                        )
    return TOOLS
