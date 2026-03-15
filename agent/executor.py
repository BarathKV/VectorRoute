import json
import ollama
from typing import List, Dict, Any, Tuple
from .models import Task, ExecutionPlan

class TaskExecutor:
    def __init__(self, agent, model: str = "llama3.1:8b"):
        """
        :param agent: The Agent instance to call its run() method for each sub-task.
        :param model: The LLM model to use for result aggregation.
        """
        self.agent = agent
        self.model = model

    def resolve_placeholders(self, query: str, completed_tasks: Dict[int, Any]) -> str:
        """Replace placeholders like <TASK_X_RESULT> with actual results."""
        resolved_query = query
        for task_id, result in completed_tasks.items():
            placeholder = f"<TASK_{task_id}_RESULT>"
            if placeholder in resolved_query:
                # If the result is a dict with 'content', extract it for better readability
                if isinstance(result, dict):
                    result_text = result.get('content') or result.get('text') or str(result)
                else:
                    result_text = str(result)
                resolved_query = resolved_query.replace(placeholder, result_text)
        return resolved_query

    def execute(self, plan: ExecutionPlan) -> Tuple[str, List[str]]:
        """Process the tasks sequentially, respecting dependencies."""
        completed_tasks = {}
        all_tools_used = []
        
        # Simple sequential execution for now, ensuring dependencies are met
        # To handle more complex DAGs efficiently, we'd need a topological sort
        # But tasks are usually returned in order or can be processed in order by checking dependencies
        
        while not plan.is_complete():
            task_executed_in_this_pass = False
            for task in plan.tasks:
                if task.status != "pending":
                    continue
                
                # Check if all dependencies are completed
                deps_met = all(dep_id in completed_tasks for dep_id in task.depends_on)
                
                if deps_met:
                    task.status = "in-progress"
                    
                    # Resolve any placeholders in the query
                    resolved_query = self.resolve_placeholders(task.query, completed_tasks)
                    
                    print(f"Executing task {task.id}: {resolved_query}")
                    # Run the individual task through the Agent's existing tool-routing logic
                    result, tools_used = self.agent.run(resolved_query)
                    
                    task.result = result
                    task.status = "completed"
                    completed_tasks[task.id] = result
                    all_tools_used.extend(tools_used)
                    task_executed_in_this_pass = True
            
            if not task_executed_in_this_pass and not plan.is_complete():
                # Avoid infinite loop if there's a circular dependency or missing task
                print("Warning: Could not make progress on task execution plan.")
                break

        # Final aggregation
        return self.aggregate_results(plan, all_tools_used)

    def aggregate_results(self, plan: ExecutionPlan, tools_used: List[str]) -> Tuple[str, List[str]]:
        """Combine all individual task results into one final user-facing response."""
        qa_pairs = []
        for task in plan.tasks:
            if isinstance(task.result, dict):
                answer_text = task.result.get("content") or task.result.get("text") or str(task.result)
            else:
                answer_text = str(task.result)
            qa_pairs.append({"task_id": task.id, "query": task.query, "answer": answer_text})

        combine_messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Combine the following task queries and their results "
                    "into a single, user-facing response that answers the user's overall goal. "
                    "Keep it clear and concise."
                ),
            },
            {"role": "user", "content": json.dumps(qa_pairs, indent=2)},
        ]

        print(f"DEBUG: Aggregating results with messages: {combine_messages}")

        try:
            combined_resp = dict(ollama.chat(model=self.model, messages=combine_messages))
            final_message = combined_resp.get("message", {"content": "Failed to aggregate results."})
            return final_message, list(set(tools_used))
        except Exception as e:
            print(f"Aggregation failed: {e}")
            return {"content": "Failed to aggregate results."}, list(set(tools_used))
