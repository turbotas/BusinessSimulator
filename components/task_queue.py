class TaskQueue:
    def __init__(self, config):
        self.config = config
        self.tasks = []  # List of tasks in the queue
        self.completed_tasks = []  # Store completed tasks for tracking

    def add_task(self, task):
        """Add a task to the queue."""
        self.tasks.append(task)
        #print(f"Task added: {task}")

    def fetch_task_for_agent(self, agent_id, role):
        """Fetch the next task matching the agent's ID or role."""
        for task in self.tasks:
            #print(f"Checking task {task['id']} for {agent_id} (Role: {role})...")
            if task.get("required_agent") == agent_id or task.get("role") == role:
                self.tasks.remove(task)
                #print(f"Task {task['id']} assigned to {agent_id} (Role: {role})")
                return task
        #print(f"No tasks available for {agent_id} (Role: {role})")
        return None

    def mark_task_completed(self, task, agent_id):
        """Mark a task as completed."""
        self.completed_tasks.append({**task, "completed_by": agent_id})
        #print(f"Task {task['id']} completed by {agent_id}")

    def get_completed_tasks(self):
        """Return all completed tasks."""
        return self.completed_tasks

    def get_all_tasks(self):
        """Return all tasks."""
        return self.tasks

    def flush_tasks(self):
        """Flush all tasks in the queue."""
        self.tasks.clear()
        print("All tasks have been flushed.")
