import csv
import argparse
from agent.agent import Agent
from agent.clasical_agent import ClassicalAgent
from tools.db_connection import DBConnection


def verify_queries(csv_path: str, agent, limit: int = None):
    results = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break
            expected_tool = row.get("Tool")
            query = row.get("Query")
            if not query:
                continue
            try:
                response, tools_used = agent.run(query)
            except Exception as e:
                results.append((i, expected_tool, None, False, f"error: {e}"))
                continue

            # Normalize tools_used to list of strings
            tools_list = tools_used or []
            match = expected_tool in tools_list
            results.append((i, expected_tool, tools_list, match, None))

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify agent tool selection against queries.csv"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit number of queries to check (default 4)",
    )
    parser.add_argument(
        "--classical", action="store_true", help="Use ClassicalAgent instead of Agent"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="io/queries.csv",
        help="Path to CSV file (default queries.csv)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="functiongemma:latest",
        help="Model to use for the agent (default functiongemma:latest)",
    )

    parser.add_argument(
        "--similarity",
        type=str,
        default="cosine",
        help="Similarity method for tool retrieval (default cosine)",
    )
    args = parser.parse_args()

    if args.similarity not in ["cosine", "ip", "l2"]:
        args.similarity = "cosine"

    db = DBConnection(similarity=args.similarity)

    agent = (
        ClassicalAgent(model=args.model, db=db)
        if args.classical
        else Agent(model=args.model, db=db)
    )

    results = verify_queries(args.csv, agent, limit=args.limit)

    total = len(results)
    matches = sum(1 for r in results if r[3] is True)
    errors = [r for r in results if r[4]]

    print(
        f"Checked {total} queries. Matches: {matches}. Mismatches: {total - matches}."
    )
    if errors:
        print("Errors during runs:")
        for e in errors:
            print(f"#{e[0]} expected={e[1]} error={e[4]}")

    if total - matches > 0:
        print("Sample mismatches:")
        for idx, expected, used, match, err in results:
            if not match and not err:
                print(f"#{idx} expected={expected} used={used}")
                # show up to 10 mismatches
                total -= 1
                if total < 0:
                    break

    # agent = Agent(model="functiongemma:latest")
    # response, tools_used = agent.run("What is the weather in New York?")
    # print(f"Response: {response}")
    # print(f"Tools used: {tools_used}")
