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
        self.message_queue = asyncio.Queue()  # Queue for incoming messages

    async def handle_command(self, command, simulation_context):
        """Handle a command given to the agent."""
        try:
            if command.startswith("message"):
                # Extract target and message
                _, target_agent, *message_parts = command.split(maxsplit=2)
                message = " ".join(message_parts)
                # Use send_message to queue the message
                return await self.send_message(target_agent, message, simulation_context)

            elif command == "list_agents":
                return f"Active agents: {simulation_context['agent_manager'].get_active_agents()}"

            elif command == "status":
                return f"{self.agent_id} is currently {self.state}."

            elif command.startswith("broadcast"):
                # Extract the message
                _, *message_parts = command.split(maxsplit=1)
                message = " ".join(message_parts)
                # Broadcast to all agents
                active_agents = simulation_context["agent_manager"].get_active_agents()
                results = []
                for agent_id in active_agents:
                    if agent_id != self.agent_id:  # Avoid sending to self
                        result = await self.send_message(agent_id, message, simulation_context)
                        results.append(result)
                return "Broadcast complete. Results:\n" + "\n".join(results)

            else:
                return f"Unknown command: {command}"

        except Exception as e:
            return f"Error handling command: {str(e)}"

    async def perform_task(self, task):
        """Perform a task using ChatGPT."""
        print(f"{self.agent_id} is performing task: {task}")
        self.state = "Active"

        # Create a task-specific prompt anchored to the agent's role
        prompt = (
            f"You are {self.params.get('name', 'an agent')}, "
            f"the {self.params.get('description', 'role description not provided')}.\n"
            f"Your role is to {self.params.get('prompt', 'act within your capacity')}.\n\n"
            f"Task: {task['description']}\n"
            "Respond in the context of your role."
        )

        # Call the AI
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

    async def send_message(self, to_agent, message, simulation_context):
        """Send a message to another agent by adding it to their message queue."""
        target_agent = simulation_context["agent_manager"].agents.get(to_agent)
        if target_agent:
            task = {
                "id": f"msg-{self.agent_id}-{len(target_agent.message_queue._queue) + 1}",
                "description": f"Message from {self.agent_id}: {message}",
                "priority": "medium"
            }
            await target_agent.message_queue.put(task)
            print(f"Message sent from {self.agent_id} to {to_agent}: {message}")
            return f"Message successfully sent to {to_agent}."
        else:
            return f"Message failed: {to_agent} not found."

    async def receive_message(self, message):
        """Receive and queue a message as a task."""
        print(f"Agent {self.agent_id} received message from {message['from']}: {message['message']}")
        task = {
            "id": f"msg-{self.agent_id}-{len(self.message_queue._queue) + 1}",
            "description": f"Message from {message['from']}: {message['message']}",
            "priority": "medium"
        }
        await self.message_queue.put(task)
        print(f"Message queued as task for {self.agent_id}: {task}")

    async def activity_loop(self):
        """Main activity loop for the agent."""
        print(f"{self.agent_id} active state: {self.active}")
        try:
            while self.active:
                # Prioritize message queue tasks
                if not self.message_queue.empty():
                    task = await self.message_queue.get()
                else:
                    # Fetch the next task from the task queue
                    task = self.task_queue.fetch_task_for_agent(self.agent_id, self.params.get("role"))

                if task:
                    print(f"{self.agent_id} picked up task: {task}")
                    await self.perform_task(task)
                else:
                    # No task available, idle briefly
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Error in activity loop for {self.agent_id}: {e}")
        finally:
            print(f"{self.agent_id} activity loop terminated. Active: {self.active}")

    def stop(self):
        """Stop the agent's activity loop."""
        self.active = False
