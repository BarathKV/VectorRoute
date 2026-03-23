import json
from typing import List
from tools.ollama_wrapper import chat_wrapper as ollama_chat
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

    def decompose(self, user_query: str, messages: List[dict]) -> ExecutionPlan:
        """Break the user query into atomic tasks using LLM."""

        system_prompt = """
            You are NOT an assistant.
            You are a QUERY DECOMPOSER.

            Your job:
            Split the user's query into tasks exactly as stated, without further breaking them down logically.

            RULES:
            - NEVER answer the query.
            - NEVER explain anything.
            - DO NOT expand or subdivide tasks beyond what is explicitly mentioned.
            - Preserve task phrasing as given in the query.
            - ONLY return valid JSON.

            Task dependency:
            If a task depends on another, reference it using <TASK_1_RESULT>.

            OUTPUT FORMAT:
            {
            "tasks": [
                {"id": 1, "query": "task text", "depends_on": []}
            ]
            }

            Example:

            Query: Find the weather in Tokyo and calculate loan EMI

            Output:
            {
            "tasks": [
                {"id": 1, "query": "Find the weather in Tokyo", "depends_on": []},
                {"id": 2, "query": "Calculate loan EMI", "depends_on": []}
            ]
            }
        """

        messages.insert(0, {"role": "system", "content": system_prompt})

        try:
            response = ollama_chat(
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

        # tasks = [Task(id=1, query=user_query, depends_on=[])]
        # return ExecutionPlan(tasks)