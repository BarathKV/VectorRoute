def search_logs(query: str, log_level: str):
    log_file = "tools/helper/documents/logs.txt"
    results = []

    with open(log_file, "r") as f:
        for line in f:
            if log_level.lower() in line.lower() and query.lower() in line.lower():
                results.append(line.strip())

    return results
