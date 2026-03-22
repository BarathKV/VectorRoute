import json
import ollama
from typing import List
from .models import Task, ExecutionPlan


class QueryDecomposer:
    def __init__(self, model: str = "llama3.1:8b"):
        self.model = model

    def _extract_json(self, content: str) -> dict:
        """Robustly extract JSON from a string that might contain LLM fluff or markdown."""
        # 1. Try direct parsing
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        # 2. Try looking for markdown code blocks
        import re

        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Try finding the first '{' and last '}'
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError("Could not extract valid JSON from LLM response")

    def decompose(self, user_query: str) -> ExecutionPlan:
        """Break the user query into atomic tasks using LLM."""

        system_prompt = """
        You are NOT an assistant.
        You are a QUERY DECOMPOSER.

        Your job:
        Split the user's query into smaller tasks.

        CRITICAL RULES:
        - NEVER answer the query.
        - NEVER explain anything.
        - ONLY split the query into tasks.
        - Return ONLY valid JSON.

        If the query contains multiple operations, create multiple tasks.

        Task dependency rule:
        If a task needs a previous task's result, reference it using <TASK_1_RESULT>.

        OUTPUT FORMAT:
        {
        "tasks": [
            {"id": 1, "query": "task text", "depends_on": []}
        ]
        }

        Example:

        Query: Find the weather in Tokyo and add 42 to 85

        Output:
        {
        "tasks": [
            {"id": 1, "query": "Find the weather in Tokyo", "depends_on": []},
            {"id": 2, "query": "Add 42 to 85", "depends_on": []}
        ]
        }
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={"temperature": 0.0, "top_p": 0.9},
                format="json",
            )
            content = response["message"]["content"]
            print(f"\n\nRAW DECOMPOSITION RESPONSE: {content}")

            data = self._extract_json(content)

            tasks = []
            for t in data.get("tasks", []):
                tasks.append(
                    Task(
                        id=t["id"], query=t["query"], depends_on=t.get("depends_on", [])
                    )
                )

            if not tasks:
                # Fallback to single task if decomposition fails
                tasks = [Task(id=1, query=user_query, depends_on=[])]

            return ExecutionPlan(tasks)

        except Exception as e:
            print(f"Decomposition failed: {e}")
            # Return single task as fallback
            return ExecutionPlan([Task(id=1, query=user_query, depends_on=[])])
