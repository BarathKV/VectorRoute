import os
import json
from typing import Set, Optional
from embedding.embedder import get_embedding

def compute_tool_embeddings(tools: list, fields: list = None, changed_tools: Optional[Set[str]] = None) -> list:
    """
    Compute embeddings for tools by selectively embedding specified fields.
    Only computes embeddings for changed tools if changed_tools is provided.
    
    Args:
        tools: List of tool capability documents
        fields: List of fields to embed. Defaults to:
                ['name', 'short_description', 'domain', 'long_description', 'example_user_queries']
        changed_tools: Optional set of tool names that have changed. If provided,
                      only these tools will have embeddings recomputed.
    
    Returns:
        List of dicts with tool, name, and embedding
    """
    # Default fields to embed
    if fields is None:
        fields = ['name', 'short_description', 'domain', 'long_description', 'example_user_queries']
    
    # Load cached embeddings if they exist
    cache_file = os.path.join(os.getcwd(), ".tool_embeddings_cache.json")
    cached_embeddings = {}
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
                for item in cached_data:
                    cached_embeddings[item['name']] = item
            print(f"Loaded {len(cached_embeddings)} cached embeddings")
        except json.JSONDecodeError:
            print("Warning: Could not load embeddings cache. Computing all embeddings.")
    
    TOOL_EMBEDDINGS = []
    computed_count = 0
    cached_count = 0

    for tool in tools:
        fn = tool["function"]
        tool_name = fn['name']
        
        # Check if we should use cached embedding
        use_cache = (changed_tools is not None and 
                    tool_name not in changed_tools and 
                    tool_name in cached_embeddings)
        
        if use_cache:
            # Use cached embedding
            cached_item = cached_embeddings[tool_name]
            TOOL_EMBEDDINGS.append({
                "tool": tool,
                "name": tool_name,
                "embedding": cached_item['embedding'],
            })
            cached_count += 1
            print(f"Using cached embedding for tool: {tool_name}")
        else:
            # Compute new embedding
            print(f"Computing embedding for tool: {tool_name}")
            
            # Extract and combine selected fields
            text_parts = []
            
            # Extract name
            if 'name' in fields and 'name' in tool:
                text_parts.append(f"Name: {tool['name']}")
            
            # Extract short_description
            if 'short_description' in fields and 'short_description' in tool:
                text_parts.append(f"Short Description: {tool['short_description']}")
            
            # Extract domain
            if 'domain' in fields and 'domain' in tool:
                text_parts.append(f"Domain: {tool['domain']}")
            
            # Extract long_description
            if 'long_description' in fields and 'long_description' in fn:
                text_parts.append(f"Long Description: {fn['long_description']}")
            
            # Extract example_user_queries
            if 'example_user_queries' in fields and 'example_user_queries' in tool:
                example_queries = tool['example_user_queries']
                if isinstance(example_queries, list) and example_queries:
                    examples_text = " | ".join(example_queries[:3])  # Limit to first 3 examples
                    text_parts.append(f"Example Queries: {examples_text}")
            
            # Combine all parts
            text = " | ".join(text_parts) if text_parts else f"Name: {tool_name}"
            
            embedding = get_embedding(text)
            computed_count += 1
            print(f"Embedding computed for tool: {tool_name}")

            TOOL_EMBEDDINGS.append(
                {
                    "tool": tool,
                    "name": tool_name,
                    "embedding": embedding,
                }
            )
    
    # Save embeddings to cache
    try:
        with open(cache_file, 'w') as f:
            json.dump(TOOL_EMBEDDINGS, f)
        print(f"\nEmbeddings cached to {cache_file}")
    except Exception as e:
        print(f"Warning: Could not save embeddings cache: {e}")
    
    print(f"\nSummary: Computed {computed_count} new embeddings, used {cached_count} cached embeddings")
    return TOOL_EMBEDDINGS
