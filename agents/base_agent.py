from openai import OpenAI
import asyncio


class BaseAgent:
    def __init__(self, agent_id, params, api_key, communication_layer, task_queue):
        """Initialize a base agent with ChatGPT capabilities."""
        self.agent_id = agent_id
        self.params = params
        self.state = "Idle"
        self.conversation = []  # Threaded conversation history
        self.client = OpenAI(api_key=api_key)  # Use the OpenAI client
        self.communication_layer = communication_layer  # Reference to communication layer
        self.task_queue = task_queue  # Reference to the task queue
        self.active = True  # Controls the agent's activity loop

    async def handle_command(self, command, simulation_context):
        """Handle a command given to the agent."""
        try:
            if command.startswith("communicate"):
                _, target_agent, *message_parts = command.split(maxsplit=2)
                message = " ".join(message_parts)
                await self.communication_layer.send_message(self.agent_id, target_agent, message)
                return f"Message sent to {target_agent}: {message}"

            elif command == "list_agents":
                return f"Active agents: {simulation_context['agent_manager'].get_active_agents()}"

            elif command == "status":
                return f"{self.agent_id} is currently {self.state}."

            elif command.startswith("assign_task"):
                _, *task_parts = command.split(maxsplit=1)
                task_desc = " ".join(task_parts)
                task = {
                    "id": len(simulation_context["task_queue"].get_all_tasks()) + 1,
                    "description": task_desc,
                    "priority": "medium",
                }
                simulation_context["task_queue"].add_task(task)
                return f"Task assigned: {task}"

            elif command.startswith("request_help"):
                _, target_agent, *task_parts = command.split(maxsplit=2)
                task_desc = " ".join(task_parts)
                await self.communication_layer.send_message(
                    self.agent_id,
                    target_agent,
                    f"Help requested with task: {task_desc}",
                )
                return f"Help requested from {target_agent} with task: {task_desc}"

            elif command.startswith("broadcast"):
                _, *message_parts = command.split(maxsplit=1)
                message = " ".join(message_parts)
                active_agents = simulation_context["agent_manager"].get_active_agents()
                for agent in active_agents:
                    if agent != self.agent_id:  # Avoid sending to self
                        await self.communication_layer.send_message(self.agent_id, agent, message)
                return f"Broadcasted message to all agents: {message}"

            else:
                return f"Unknown command: {command}"

        except Exception as e:
            return f"Error handling command: {str(e)}"

    async def perform_task(self, task):
        """Perform a task using ChatGPT."""
        print(f"{self.agent_id} is performing task: {task}")
        self.state = "Active"

        # Create a task-specific prompt
        prompt = f"Task Description: {task['description']}\n{self.params.get('instructions', '')}"
        response = await self.query_chatgpt(prompt)

        # Process the response
        result = {
            "task_id": task["id"],
            "response": response
        }

        # Notify the task queue
        self.task_queue.mark_task_completed(task, self.agent_id)

        self.state = "Idle"
        print(f"{self.agent_id} completed task: {result}")
        return result

    async def query_chatgpt(self, user_input):
        """Query ChatGPT with user input and maintain threaded conversation."""
        # Add user input to the conversation
        self.conversation.append({"role": "user", "content": user_input})

        try:
            # Correct API usage for OpenAI v1.57.0
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=self.conversation
            )

            # Extract the message content correctly
            chat_response = response.choices[0].message.content
            self.conversation.append({"role": "assistant", "content": chat_response})

            return chat_response

        except Exception as e:
            return f"Error querying ChatGPT: {str(e)}"

    async def send_message(self, to_agent, message):
        """Send a message to another agent."""
        await self.communication_layer.send_message(self.agent_id, to_agent, message)

    async def receive_message(self, message):
        """Receive and handle a message."""
        print(f"Agent {self.agent_id} received message from {message['from']}: {message['message']}")
        # Process the message (extend logic as needed)
        if message["message"].lower() == "status":
            return f"{self.agent_id} is currently {self.state}."
        else:
            return f"Message received: {message['message']}"

    async def activity_loop(self):
        """Main activity loop for the agent."""
        print(f"{self.agent_id} active state: {self.active}")
        try:
            while self.active:
                if not self.active:  # Check in case it was paused mid-loop
                    break
                # Fetch the next task matching this agent's role or ID
                #print(f"{self.agent_id} is polling for tasks...")
                task = self.task_queue.fetch_task_for_agent(self.agent_id, self.params.get("role"))
                if task:
                    print(f"{self.agent_id} picked up task: {task}")
                    await self.perform_task(task)
                else:
                    # No task available, idle briefly
                    #print(f"{self.agent_id} found no tasks. Idling...")
                    await asyncio.sleep(5)
        except Exception as e:
            print(f"Error in activity loop for {self.agent_id}: {e}")
        finally:
            print(f"{self.agent_id} activity loop terminated. Active: {self.active}")

    def stop(self):
        """Stop the agent's activity loop."""
        self.active = False

