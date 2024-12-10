from openai import OpenAI
import asyncio


class BaseAgent:
    COMMAND_DEFINITIONS = {
        "message": {
            "description": "Send a message to another agent.",
            "syntax": "message <target_agent_id> <message>"
        },
        "list_agents": {
            "description": "List all active agents.",
            "syntax": "list_agents"
        },
        "status": {
            "description": "Report the current status of the agent.",
            "syntax": "status"
        },
        "broadcast": {
            "description": "Send a message to all other agents.",
            "syntax": "broadcast <message>"
        },
        "flush_tasks": {
            "description": "Flush the entire task queue accross the organisation.",
            "syntax": "flush_tasks"
        },
        "terminate_agent": {
            "description": "Terminate and remove a specific agent.",
            "syntax": "terminate_agent <agent_id>"
        }
    }
    
    def __init__(self, agent_id, params, api_key, agent_manager, task_queue, gpt_version, communication_layer):
        """Initialize a base agent with ChatGPT compatible capabilities."""
        self.agent_id = agent_id
        self.params = params
        self.state = "Idle"
        self.conversation = []  # Threaded conversation history
        self.client = OpenAI(api_key=api_key)  # Use the OpenAI client
        self.agent_manager = agent_manager  # Reference to the AgentManager 
        self.task_queue = task_queue  # Reference to the task queue
        self.active = True  # Controls the agent's activity loop
        self.gpt_version = gpt_version  # GPT version to use
        self.message_queue = asyncio.Queue()  # Queue for incoming messages
        # Extract boss and subordinates for easy access
        self.boss = params.get("boss", "No direct supervisor")
        self.subordinates = params.get("subordinates", [])
        self.communication_layer = communication_layer  # Reference to communication layer

    async def handle_command(self, command, simulation_context):
        """Handle a command given to the agent."""
        try:
            #print(f"DEBUG: Received command: {command}")  # Debug received command
            #print(f"DEBUG: Simulation context: {simulation_context}")  # Debug simulation context
            if command.startswith("message"):
                # Extract target and message
                _, target_agent, *message_parts = command.split(maxsplit=2)
                message = " ".join(message_parts)
                # Use send_message to queue the message
                return await self.send_message(target_agent, message, simulation_context)
            elif command.startswith("list_agents"):
                return f"Active agents: {simulation_context['agent_manager'].get_active_agents()}"
            elif command.startswith("status"):
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
            elif command.startswith("flush_tasks"):
                simulation_context["task_queue"].flush_tasks()
                return "Task queue flushed successfully."
            elif command.startswith("terminate_agent"):
                _, target_agent = command.split(maxsplit=1)
                result = simulation_context["agent_manager"].terminate_agent(target_agent)
                return result
            else:
                return f"Unknown command: {command}"

        except Exception as e:
            return f"Error handling command: {str(e)}"

    async def perform_task(self, task):
        """Perform a task using ChatGPT."""
        print(f"\033[32m{self.agent_id}\033[0m is performing task: {task}")
        self.state = "Active"
        
        # Generate the command help text
        commands_help = "\n".join(
            [f"{cmd}: {info['description']} (Syntax: {info['syntax']})"
             for cmd, info in self.COMMAND_DEFINITIONS.items()]
        )

        # Fetch the full list of staff (agents) directly from the AgentManager
        staff_list = ", ".join(self.agent_manager.get_active_agents())

        # Create a task-specific prompt anchored to the agent's role
        prompt = (
            f"You are {self.params.get('name', 'an agent')}, "
            f"the {self.params.get('description', 'role description not provided')}.\n"
            f"Your role is: {self.params.get('prompt', 'act within your capacity')}.\n\n"
            f"Commands you can execute (each command on it's own line) to help you reach your goals:\n{commands_help}\n\n"
            f"Your direct supervisor is: {self.params.get('boss')}.\n"
            f"Your direct reports are: {self.subordinates}.\n\n"
            f"The full list of staff in this organization is: {staff_list}.\n\n"
            f"Task: {task['description']}\n"
            "Respond in the context of your role. be precise and succinct.  You should not respond unless you have something useful to say. Your response will not be seen by the other person unless you sent it to them using a command, but you should not sommunicate unless you need to to accomplish your task."
        )

        # Debug: Print the full prompt
        #print(f"DEBUG: Full prompt for {self.agent_id}:\n{prompt}\n")

        # Call the AI
        response = await self.query_chatgpt(prompt)

        # Process the response
        result = {
            "task_id": task["id"],
            "gpt": self.gpt_version,
            "response": response
        }

        # Process the response:
        await self.process_ai_response(response)

        # Notify the task queue
        self.task_queue.mark_task_completed(task, self.agent_id)

        self.state = "Idle"
        #print(f"{self.agent_id} completed task: {result}")
        return result

    async def query_chatgpt(self, user_input):
        """Query ChatGPT with user input and maintain threaded conversation."""
        # Add user input to the conversation
        self.conversation.append({"role": "user", "content": user_input})

        try:
            # Correct API usage for OpenAI v1.57.0
            # print(f"[DEBUG] {self.agent_id} using GPT model {self.gpt_version} for request.")
            response = self.client.chat.completions.create(
                model=self.gpt_version,
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
            print(f"Message sent from \033[32m{self.agent_id}\033[0m to \033[32m{to_agent}\033[0m: {message}")
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
        #print(f"{self.agent_id} active state: {self.active}")
        try:
            while self.active:
                # Prioritize message queue tasks
                if not self.message_queue.empty():
                    task = await self.message_queue.get()
                else:
                    # Fetch the next task from the task queue
                    task = self.task_queue.fetch_task_for_agent(self.agent_id, self.params.get("role"))

                if task:
                    #print(f"{self.agent_id} picked up task: {task}")
                    await self.perform_task(task)
                else:
                    # No task available, idle briefly
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Error in activity loop for {self.agent_id}: {e}")
        finally:
            print(f"{self.agent_id} activity loop terminated. Active: {self.active}")

    async def process_ai_response(self, response):
        """Parse and execute multiple commands from the AI's response."""
        response = response.strip()
        #print(f"DEBUG: Processing AI response: {response}")  # Debug line to log the entire response

        # Split the response into individual lines
        commands = response.splitlines()

        # Process each line as a separate command
        for line in commands:
            line = line.strip()  # Remove any leading/trailing whitespace
            if not line:  # Skip empty lines
                continue

            # Check if the line starts with a recognized command
            if line.startswith(tuple(self.COMMAND_DEFINITIONS.keys())):
                command_parts = line.split(maxsplit=1)
                command = command_parts[0]
                arguments = command_parts[1] if len(command_parts) > 1 else ""
                print(f"\033[32m{self.agent_id}\033[0m: \033[34m{command}\033[0m {arguments}")

                # Execute the command
                result = await self.handle_command(
                    f"{command} {arguments}",
                    {
                        "agent_manager": self.agent_manager,
                        "task_queue": self.task_queue
                    }
                )
                print(f"Command result: {result}")
            else:
                print(f"\033[32m{self.agent_id}\033[0m: {line}")


    def stop(self):
        """Stop the agent's activity loop."""
        self.active = False
