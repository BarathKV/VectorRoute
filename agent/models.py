from typing import List, Optional, Any

class Task:
    def __init__(self, id: int, query: str, depends_on: Optional[List[int]] = None):
        self.id = id
        self.query = query
        self.depends_on = depends_on or []
        self.result: Any = None
        self.status: str = "pending"  # pending, in-progress, completed, failed

    def to_dict(self):
        return {
            "id": self.id,
            "query": self.query,
            "depends_on": self.depends_on,
            "status": self.status
        }

class ExecutionPlan:
    def __init__(self, tasks: List[Task]):
        self.tasks = tasks

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def is_complete(self) -> bool:
        return all(task.status == "completed" for task in self.tasks)
