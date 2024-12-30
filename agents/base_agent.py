from openai import AsyncOpenAI
from components.command_processor import CommandProcessor

import asyncio

class BaseAgent:
    MAX_CONVERSATION_LENGTH = 10  # Limit to the last 10 exchanges
    COMMAND_DEFINITIONS = {
        "message_agent": {
            "description": "Send a message to another agent.",
            "syntax": "message_agent <target_agent_id> <message>"
        },
        "message_role": {
            "description": "Send a message to all agents with given role.",
            "syntax": "message_role <role_id> <message>"
        },
        "list_agents": {
            "description": "List all active agents (response format: agent_id:role)",
            "syntax": "list_agents"
        },
        "list_roles": {
            "description": "List all possible roles.",
            "syntax": "list_roles"
        },
        "spawn": {
            "description": "Create a new agent with the given role.",
            "syntax": "spawn <role>"
        },
        "status": {
            "description": "Report the current status of the current agent. Normally this is for admin purposes only.",
            "syntax": "status"
        },
        "broadcast": {
            "description": "Send a message to all other agents. Only use this for important communications that every agent must see. Probably it needs your boss to carry this out.",
            "syntax": "broadcast <message>"
        },
        "flush_tasks": {
            "description": "Flush the entire task queue accross the organisation. Only carry this out if you want the whole organisation to stop working.",
            "syntax": "flush_tasks"
        },
        "terminate_agent": {
            "description": "Terminate and remove a specific agent. Normally this would be one of your direct reports.",
            "syntax": "terminate_agent <agent_id>"
        }
    }
    
    def __init__(self, agent_id, params, api_key, agent_manager, task_queue, gpt_version, communication_layer, roles_library, command_processor):
        """Initialize a base agent with ChatGPT compatible capabilities."""
        self.agent_id = agent_id
        self.params = params
        self.state = "Idle"
        self.conversation = []  # Threaded conversation history
        self.client = AsyncOpenAI(api_key=api_key)  # Use the OpenAI client
        self.agent_manager = agent_manager  # Reference to the AgentManager 
        self.task_queue = task_queue  # Reference to the task queue
        self.active = True  # Controls the agent's activity loop
        self.gpt_version = gpt_version  # GPT version to use
        self.message_queue = asyncio.Queue()  # Queue for incoming messages
        self.roles_library = roles_library  # Store the roles library
        self.command_processor = command_processor  # Pass the command processor directly
        # Extract boss and subordinates for easy access
        self.boss = params.get("boss", "No direct supervisor")
        self.subordinates = params.get("subordinates", [])
        self.communication_layer = communication_layer  # Reference to communication layer

    async def handle_command(self, command, simulation_context):
        """Handle a command given to the agent."""
        try:
            #print(f"DEBUG: Received command: {command}")  # Debug received command
            #print(f"DEBUG: Simulation context: {simulation_context}")  # Debug simulation context
            if command.startswith("message_agent"):
                # Extract target and message
                _, target_agent, *message_parts = command.split(maxsplit=2)
                message = " ".join(message_parts)
                # Use send_message to queue the message
                return await self.send_message_agent(target_agent, message, simulation_context)
            elif command.startswith("message_role"):
                # Extract target and message
                _, target_role, *message_parts = command.split(maxsplit=2)
                message = " ".join(message_parts)
                # Use send_message to queue the message
                return await self.send_message_role(target_role, message, simulation_context)
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
            elif command.startswith("list_roles"):
                print(f"DEBUG: {self.agent_id} is invoking command_processor for 'list_roles'.")
                
                # Use the command processor to handle the 'list_roles' request
                result = self.command_processor.process_command("list_roles", {
                    "caller": self.agent_id,
                    "agent_manager": simulation_context["agent_manager"],
                    "roles_library": simulation_context["roles_library"]
                })
                print(f"DEBUG: {self.agent_id} got result back from command_processor: {result}")
                return result  
            else:
                return f"Unknown command: {command}"

        except Exception as e:
            return f"Error handling command: {str(e)}"

    async def perform_task(self, task):
        """Perform a task using ChatGPT."""
        self.state = "Active"

        # Generate the command help text dynamically
        commands_help = "\n".join(
            [f"{cmd}: {info['description']} (Syntax: {info['syntax']})"
             for cmd, info in self.COMMAND_DEFINITIONS.items()]
        )
        
        # Dynamically fetch the current list of agents with roles
        current_agent_list = ", ".join(
            f"{agent_id} ({agent.params.get('role', 'Unknown Role')})"
            for agent_id, agent in self.agent_manager.agents.items()
        )

        # Static system prompt with dynamic agent list
        system_prompt = (
            f"You are agent {self.agent_id}, "
            f"the {self.params.get('description', 'role description not provided')}.\n"
            f"{self.params.get('prompt', 'act within your capacity')}.\n\n"
            f"Commands you can execute are:\n{commands_help}.\n"
            "Commands must start on a blank line. If you have no command, nothing will be done.\n\n"
            f"Your direct supervisor by role_id is: {self.params.get('boss', 'None')}.\n"
            f"Your direct reports by role_id are: {', '.join(self.subordinates) or 'None'}.\n\n"
            f"The current list of agents in this organization is: {current_agent_list}."

        )

        # Task-specific user prompt
        task_prompt = (
            f"Task: {task['description']}\n"
            "Respond in the context of your role. Be precise and succinct. Only communicate if necessary "
            "to achieve your task. Use at least one command unless no action is required. "
            "Multiple commands must each start on their own line. Previous chat history is provided with you as 'Assistant'. DO NOT simply send innanities back and forth."
        )

        # Query the AI with the clean conversation history
        response = await self.query_chatgpt(system_prompt, task_prompt)

        # Append the user prompt and AI response to conversation history
        self.append_to_conversation("user", task_prompt)
        self.append_to_conversation("assistant", response)

        # Debug: Print the response for clarity
        print(f"\033[32mDEBUG: AI Response for {self.agent_id}:\033[0m\n{response}\n")

        # Process the response for any commands
        await self.process_ai_response(response)

        # Notify the task queue that the task is completed
        self.task_queue.mark_task_completed(task, self.agent_id)

        self.state = "Idle"
        return {"task_id": task["id"], "gpt": self.gpt_version, "response": response}

    async def query_chatgpt(self, system_prompt, task_prompt):
        """Query ChatGPT asynchronously and maintain clean conversation history."""
        # Construct the conversation with the system prompt and clean history
        conversation = [{"role": "system", "content": system_prompt}]
        conversation.extend(self.get_conversation_history())  # Append existing clean history
        conversation.append({"role": "user", "content": task_prompt})  # Append current task prompt

        # Debug: Print the full conversation
        print("\033[34mDEBUG: Full Conversation Sent to GPT:\033[0m")
        for idx, msg in enumerate(conversation):
            print(f"  [{idx}] {msg['role'].capitalize()}: {msg['content']}")
        print("")

        try:
            # Make the asynchronous GPT API call
            response = await self.client.chat.completions.create(
                model=self.gpt_version,
                messages=conversation
            )
            return response.choices[0].message.content

        except Exception as e:
            print(f"Error querying ChatGPT for {self.agent_id}: {e}")
            return f"Error querying ChatGPT: {str(e)}"

    def append_to_conversation(self, role, content):
        """Add a new message to the conversation history."""
        self.conversation.append({"role": role, "content": content})
        self.truncate_conversation()

    def get_conversation_history(self):
        """Retrieve the last N exchanges from the conversation history."""
        return self.conversation[-self.MAX_CONVERSATION_LENGTH * 2:]  # Each exchange includes user and assistant

    def truncate_conversation(self):
        """Limit the conversation history to avoid exponential growth."""
        if len(self.conversation) > self.MAX_CONVERSATION_LENGTH * 2:
            self.conversation = self.conversation[-self.MAX_CONVERSATION_LENGTH * 2:]

    async def send_message_agent(self, to_agent, message, simulation_context):
        """Send a message to another agent by adding it to their message queue."""
        target_agent = simulation_context["agent_manager"].agents.get(to_agent)
        if target_agent:
            task = {
                "id": f"msg-{self.agent_id}-{len(target_agent.message_queue._queue) + 1}",
                "description": f"Message from {self.agent_id}: {message}",
                "priority": "medium"
            }
            await target_agent.message_queue.put(task)
            #print(f"Message sent from \033[32m{self.agent_id}\033[0m to \033[32m{to_agent}\033[0m: {message}")
            return f"Message successfully sent to {to_agent}."
        else:
            return f"Message failed: {to_agent} not found."

    async def send_message_role(self, role_name, message, simulation_context):
        """Send a message to all agents with the specified role."""
        agent_manager = simulation_context["agent_manager"]
        matching_agents = [
            agent for agent_id, agent in agent_manager.agents.items()
            if agent.params.get("role") == role_name
        ]

        if not matching_agents:
            return f"No agents found with role '{role_name}'."

        # Send the message to each matching agent
        for target_agent in matching_agents:
            task = {
                "id": f"msg-{self.agent_id}-{len(target_agent.message_queue._queue) + 1}",
                "description": f"Message from {self.agent_id}: {message}",
                "priority": "medium"
            }
            await target_agent.message_queue.put(task)

        return f"Message successfully sent to {len(matching_agents)} agents with role '{role_name}'."

    async def receive_message(self, message):
        """Receive and queue a message as a task."""
        #print(f"Agent {self.agent_id} received message from {message['from']}: {message['message']}")
        task = {
            "id": f"msg-{self.agent_id}-{len(self.message_queue._queue) + 1}",
            "description": f"Message from {message['from']}: {message['message']}",
            "priority": "medium"
        }
        await self.message_queue.put(task)
        #print(f"Message queued as task for {self.agent_id}: {task}")

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
                        "task_queue": self.task_queue,
                        "roles_library": self.agent_manager.roles_library  # Ensure roles_library is passed
                    }
                )
                #print(f"Command result: {result}")
            else:
                print(f"\033[32m{self.agent_id}\033[0m: {line}")
    
    def get_info(self):
        """Return all relevant details about the agent."""
        return {
            "Agent ID": self.agent_id,
            "Name": self.params.get("name", "Unknown"),
            "Role": self.params.get("role", "Unknown"),
            "Description": self.params.get("description", "No description provided."),
            "State": self.state,
            "Boss": self.boss or "None",
            "Subordinates": ", ".join(self.subordinates) if self.subordinates else "None",
            "GPT Version": self.gpt_version,
            "Task Queue Size": len(self.task_queue.get_all_tasks()),
            "Message Queue Size": self.message_queue.qsize(),
            "Conversation History": len(self.conversation),
        }
    
    def stop(self):
        """Stop the agent's activity loop."""
        self.active = False
