def apply_filters(results, query: str, capabilities: dict):
    filtered = []

    for r in results:
        cap = capabilities[r["server_id"]]

        # Simple keyword exclusion example
        if "news" in query.lower():
            if "news" not in cap["domain"].lower():
                continue

        filtered.append(r)

    return filtered