from model.embedding import get_embedding


def compute_tool_embeddings(tools: list, fields: list = None) -> list:
    """
    Compute embeddings for tools by selectively embedding specified fields.
    
    Args:
        tools: List of tool capability documents
        fields: List of fields to embed. Defaults to:
                ['name', 'short_description', 'domain', 'long_description', 'example_user_queries']
    
    Returns:
        List of dicts with tool, name, and embedding
    """
    # Default fields to embed
    if fields is None:
        fields = ['name', 'short_description', 'domain', 'long_description', 'example_user_queries']
    
    TOOL_EMBEDDINGS = []

    for tool in tools:
        fn = tool["function"]
        tool_name = fn['name']
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
        print(f"Embedding computed for tool: {tool_name}")

        TOOL_EMBEDDINGS.append(
            {
                "tool": tool,
                "name": tool_name,
                "embedding": embedding,
            }
        )
    return TOOL_EMBEDDINGS
