import time

class PerformanceMonitor:
    def __init__(self, config):
        """Initialize the performance monitor."""
        self.config = config
        self.start_time = None
        self.metrics = {
            "total_tasks_completed": 0,
            "average_task_duration": 0.0,
            "agent_task_counts": {},  # Tracks task count per agent
            "agent_task_durations": {},  # Tracks total task duration per agent
        }

    def start_simulation_timer(self):
        """Start the simulation runtime timer."""
        self.start_time = time.time()

    def stop_simulation_timer(self):
        """Stop the timer and return total runtime."""
        if self.start_time:
            return time.time() - self.start_time
        return 0

    def log_task_completion(self, agent_id, task_id, duration):
        """Log a completed task."""
        self.metrics["total_tasks_completed"] += 1

        # Update average task duration
        total_duration = self.metrics["average_task_duration"] * (
            self.metrics["total_tasks_completed"] - 1
        )
        self.metrics["average_task_duration"] = (total_duration + duration) / self.metrics["total_tasks_completed"]

        # Update agent-specific metrics
        if agent_id not in self.metrics["agent_task_counts"]:
            self.metrics["agent_task_counts"][agent_id] = 0
            self.metrics["agent_task_durations"][agent_id] = 0.0

        self.metrics["agent_task_counts"][agent_id] += 1
        self.metrics["agent_task_durations"][agent_id] += duration

    def get_system_metrics(self):
        """Return a summary of system metrics."""
        runtime = self.stop_simulation_timer() if self.start_time else 0
        return {
            "runtime": runtime,
            "total_tasks_completed": self.metrics["total_tasks_completed"],
            "average_task_duration": self.metrics["average_task_duration"],
            "agent_task_counts": self.metrics["agent_task_counts"],
            "agent_task_durations": self.metrics["agent_task_durations"],
        }

