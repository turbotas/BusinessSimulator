from agents.base_agent import BaseAgent

class DataAnalystAgent(BaseAgent):
    def perform_task(self, task):
        """Perform a data analysis task using ChatGPT."""
        print(f"{self.agent_id} is analyzing data: {task['description']}")
        self.state = "Active"

        # Custom task prompt for data analysis
        prompt = f"Analyze the following dataset and provide insights:\n{task['description']}\n{self.params.get('dataset', '')}"
        response = self.query_chatgpt(prompt)

        # Process the response
        result = {
            "task_id": task["id"],
            "response": response,
            "insights": f"Extracted insights: {response}"
        }

        self.state = "Idle"
        return result

