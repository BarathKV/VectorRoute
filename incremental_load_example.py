"""
Example usage of incremental tool embedding computation with file change tracking.
This script demonstrates how to:
1. Track file changes in VectorRoute-Tools
2. Only compute embeddings for modified tools
3. Cache and reuse embeddings for unchanged tools
"""

from tool_utils.tool_registry import update_tool_registry
from tool_utils.fetch_tool_docs import fetch_tool_docs
from tool_utils.file_tracker import FileChangeTracker
from embedding.tool_embedder import compute_tool_embeddings

def main():
    # Initialize file change tracker
    tracker = FileChangeTracker()
    
    # Check for file changes
    print("=" * 60)
    print("Checking for file changes in VectorRoute-Tools...")
    print("=" * 60)
    changed_tools = tracker.get_changed_tools()
    
    if changed_tools:
        print(f"\nFound {len(changed_tools)} tools with changes:")
        for tool_name in sorted(changed_tools):
            print(f"  - {tool_name}")
    else:
        print("\nNo changes detected since last run.")
    
    # Load tool registry and documentation
    print("\n" + "=" * 60)
    print("Loading tool registry and documentation...")
    print("=" * 60)
    tool_registry = update_tool_registry()
    tool_doc_list = fetch_tool_docs()
    
    # Compute embeddings (only for changed tools if any)
    print("\n" + "=" * 60)
    print("Computing tool embeddings...")
    print("=" * 60)
    
    if changed_tools:
        # Incremental mode: only compute for changed tools
        tool_embeddings = compute_tool_embeddings(
            tool_doc_list, 
            changed_tools=changed_tools
        )
    else:
        # Try to use all cached embeddings
        tool_embeddings = compute_tool_embeddings(
            tool_doc_list,
            changed_tools=set()  # Empty set means no changes, use all cached
        )
    
    # Mark files as processed (update the cache)
    print("\n" + "=" * 60)
    print("Updating file change cache...")
    print("=" * 60)
    tracker.mark_as_processed()
    
    print("\n" + "=" * 60)
    print(f"Processing complete! Total embeddings: {len(tool_embeddings)}")
    print("=" * 60)
    
    return tool_registry, tool_embeddings

if __name__ == "__main__":
    tool_registry, tool_embeddings = main()
    
    # Now you can use tool_registry and tool_embeddings with your agent
    # Example:
    # from agent.agent import Agent
    # agent = Agent(tool_registry, tool_embeddings)
