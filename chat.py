import argparse
import os
import sys

from tools.tool_registry import update_tool_registry
from tools.fetch_tool_docs import fetch_tool_docs
from embedding.tool_embedder import compute_tool_embeddings
from tools.file_tracker import FileChangeTracker
from agent.agent import Agent


def init_agent(model: str = "functiongemma:latest") -> Agent:
    tracker = FileChangeTracker()
    changed_tools = tracker.get_changed_tools()

    if changed_tools:
        print(f"Detected {len(changed_tools)} tools with changes. Recomputing embeddings...")
    else:
        print("No tool changes detected. Using cached embeddings.")

    tool_registry = update_tool_registry()
    tool_doc_list = fetch_tool_docs()

    tool_embedding = compute_tool_embeddings(
        tool_doc_list,
        changed_tools=changed_tools,
    )

    tracker.mark_as_processed()

    agent = Agent(tool_registry, tool_embedding, model=model)
    return agent


def _extract_message_content(response) -> str:
    # Agent.run() returns (response, tools_used). Response can be a dict
    # returned by `ollama.chat` or a plain string error. Handle both.
    if isinstance(response, dict):
        message = response.get("message") or {}
        if isinstance(message, dict):
            return message.get("content") or str(message)
        return str(message)
    return str(response)


def _normalize_and_format_reply(content: str) -> str:
    """Normalize reply text and format newline markers consistently.

    Replaces common literal newline markers ("\\n" and "/n") with real
    newlines, collapses multiple blank lines, trims whitespace on each line,
    and returns the joined result. This is intentionally generic and does not
    try to parse domain-specific content.
    """
    if not isinstance(content, str):
        content = str(content)

    # Replace common literal newline representations with actual newlines
    content = content.replace('\\n', '\n')
    content = content.replace('/n', '\n')

    # Split into lines, strip each, and remove empty lines
    lines = [ln.strip() for ln in content.splitlines()]
    lines = [ln for ln in lines if ln]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    # parser.add_argument("--model", default="llama3.2:3b", help="Ollama model to use")
    parser.add_argument("--model", default="functiongemma:latest", help="Ollama model to use")
    args = parser.parse_args()

    agent = init_agent(args.model)

    print(f"Chat ready with model {args.model}. Press Ctrl-D to exit.")

    try:
        while True:
            try:
                user_input = input("You: ")
            except EOFError:
                print("\nGoodbye.")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            response, tools_used = agent.run(user_input)
            content = _extract_message_content(response)

            # Extract and print only the content between `content='` and `' thinking`
            start = content.find("content='") + len("content='")
            end = content.find("' thinking")
            if start != -1 and end != -1:
                print("Assistant:")
                print(content[start:end].strip())

    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")


if __name__ == "__main__":
    main()
