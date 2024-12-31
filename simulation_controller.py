import json
import asyncio
import aioconsole
import os
import argparse
from components.agent_manager import AgentManager
from components.task_queue import TaskQueue
from components.performance_monitor import PerformanceMonitor
from components.communication_layer import CommunicationLayer
from components.global_context import GlobalContext
from components.command_processor import CommandProcessor
from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the simulation with a specified meta configuration.")
    parser.add_argument(
        "--meta_config",
        type=str,
        default="config/meta_config.json",
        help="Path to the meta configuration file."
    )
    args = parser.parse_args()

class SimulationController:
    def __init__(self, config_file="config/default_config.json", meta_config_file="config/meta_config.json"):
        """Initialize the simulation controller."""
        self.running = False
        self.initializing = False
        self.config_file = config_file
        self.meta_config_file = meta_config_file
        
        self.config = self.load_config(config_file)
        
        # 1) Call load_meta_config early to populate roles_library, initial_agents, etc.
        self.roles_library = {}
        self.initial_agents = []
        self.initial_tasks = []
        self.load_meta_config()  # Now self.roles_library is filled if the meta config is present
        
        # 2) Create placeholders for other items
        self.agent_manager = None
        self.task_queue = None
        self.performance_monitor = None
        self.communication_layer = None
        
        # 3) Build the global context using the newly populated roles_library
        self.global_context = GlobalContext(
            roles_library=self.roles_library,
            agent_manager=self.agent_manager,
            task_queue=self.task_queue,
            performance_monitor=self.performance_monitor,
            communication_layer=self.communication_layer
        )
        
        # 4) Create the command processor with the global context
        self.command_processor = CommandProcessor(self.global_context)    

    def load_config(self, file_path):
        """Load configuration from a JSON file."""
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Configuration file not found: {file_path}")
            return {}

    def load_meta_config(self):
        """Load the meta-configuration file and separate roles, agents, and tasks."""
        try:
            with open(self.meta_config_file, "r") as f:
                meta_config = json.load(f)
                self.roles_library = {role["role"]: role for role in meta_config.get("roles", [])}
                self.initial_agents = meta_config.get("initial_agents", [])
                self.initial_tasks = meta_config.get("initial_tasks", [])
                
                print(f"Roles Library Loaded: {self.roles_library}")
                print(f"Initial Agents Loaded: {self.initial_agents}")
                print(f"Initial Tasks Loaded: {self.initial_tasks}")
                return meta_config
        except FileNotFoundError:
            print(f"Meta-config file not found: {self.meta_config_file}")
            return {}

    async def initialize(self):
        if self.initializing:
            print("Initialization is already in progress.")
            return

        self.initializing = True
        print("Initializing simulation environment...")

        self.performance_monitor = PerformanceMonitor(self.config.get("performance_monitor", {}))
        api_key = os.getenv("OPENAI_API_KEY")
        self.task_queue = TaskQueue(self.config.get("task_queue", {}))
        self.communication_layer = CommunicationLayer()

        self.agent_manager = AgentManager(
            self.config.get("agent_manager", {}),
            self.performance_monitor,
            api_key,
            self.communication_layer,
            self.task_queue,
            self.roles_library,
            self.command_processor
        )

        # Update the global context references now that we've created them
        self.global_context.agent_manager = self.agent_manager
        self.global_context.task_queue = self.task_queue
        self.global_context.performance_monitor = self.performance_monitor
        self.global_context.communication_layer = self.communication_layer

        try:
            await self.initialize_agents()  # Spawn initial agents
            self.assign_initial_tasks()
            print("Simulation environment initialized.")
            self.running = True
        except Exception as e:
            print(f"Error during initialization: {e}")
        finally:
            self.initializing = False

    async def initialize_agents(self):
        """Initialize agents based on the initial_agents list in the meta-config."""
        print("DEBUG: Starting agent initialization.")  # Debug statement
        print(f"DEBUG: Initial agents: {self.initial_agents}")  # Debug initial agents
        print(f"DEBUG: Roles Library: {self.roles_library}")  # Debug roles library
        print(f"DEBUG: Command Processor: {self.command_processor}")  # Debug command processor
        
        tasks = []  # Define async tasks for agent creation
        for agent in self.initial_agents:
            role_params = self.roles_library.get(agent["role"], {})
            if not role_params:
                print(f"Role {agent['role']} not found in the role library. Skipping agent {agent['name']}.")
                continue

            print(f"DEBUG: Preparing to spawn agent {agent['name']} with role {agent['role']}.")

            agent_params = {
                "name": agent.get("name"),
                "description": role_params.get("description", "No description provided."),
                "prompt": role_params.get("prompt", ""),
                "boss": role_params.get("boss"),
                "subordinates": role_params.get("subordinates", []),
                "role": agent["role"],
                "gpt_version": role_params.get("gpt_version", self.config.get("chatgpt_agent", {}).get("default_gpt_version", "gpt-4"))
            }

            # Debug agent parameters
            #print(f"DEBUG: Agent parameters: {agent_params}")
            #print(f"DEBUG: self.command_processor: {self.command_processor}")  # Check the value of command_processor


            # Pass the CommandProcessor instance when spawning the agent
            tasks.append(asyncio.create_task(
                self.agent_manager.spawn_agent("BaseAgent", agent_params, self.command_processor)
            ))

        # Periodic progress reporting
        for i, task in enumerate(asyncio.as_completed(tasks), start=1):
            await task
        print(f"DEBUG: Initialized {i} agents...")

        # Await all tasks to complete
        await asyncio.gather(*tasks)

    def assign_initial_tasks(self):
        """Assign initial tasks based on the initial_tasks section in the meta-config."""
        if not self.initial_tasks:
            print("No initial tasks to assign.")
            return

        for task in self.initial_tasks:
            assigned_role = task.get("assigned_role")
            if assigned_role in self.roles_library:
                task_to_add = {
                    "id": len(self.task_queue.get_all_tasks()) + 1,
                    "description": task["description"],
                    "priority": "medium",
                    "role": assigned_role
                }
                self.task_queue.add_task(task_to_add)
                print(f"Assigned initial task: {task_to_add}")
            else:
                print(f"Task skipped: Assigned role {assigned_role} not found in roles library.")

    async def start_simulation(self):
        """Start the simulation."""
        if self.running:
            print("Simulation is already running.")
            return

        if self.initializing:
            print("Simulation is still initializing. Please wait.")
            return

        print("Starting simulation...")
        await self.initialize()
        print("Simulation started.")

    def pause_simulation(self):
        """Pause the simulation."""
        if not self.running:
            print("Simulation is not running.")
            return

        print("Pausing simulation...")
        self.running = False

        # Notify all agents to stop their activity loops
        for agent_id in self.agent_manager.get_active_agents():
            self.agent_manager.agents[agent_id].stop()

        print("Simulation paused.")

    def resume_simulation(self):
        """Resume the simulation."""
        if self.running:
            print("Simulation is already running.")
            return

        print("Resuming simulation...")
        self.running = True

        # Notify all agents to resume their activity loops
        for agent_id in self.agent_manager.get_active_agents():
            agent = self.agent_manager.agents[agent_id]
            if not agent.active: # only restart if the agent was stopped
                agent.active = True
                asyncio.create_task(agent.activity_loop())

        print("Simulation resumed.")

    def stop_simulation(self):
        """Stop the simulation."""
        if not self.running:
            print("Simulation is not running.")
            return

        print("Stopping simulation...")
        self.running = False

        # Terminate all agents
        active_agents = self.agent_manager.get_active_agents()
        for agent_id in active_agents:
            self.agent_manager.terminate_agent(agent_id)

        # Clear tasks
        self.task_queue.clear_tasks()

        print("Simulation stopped.")

    def debug_agent(self, agent_id):
        """Print detailed debug information for a specific agent."""
        agent_id = str(agent_id)  # Ensure agent_id is treated as a string
        print(f"DEBUG: Looking for agent with ID '{agent_id}'...")

        # Fetch the agent
        agent = self.agent_manager.agents.get(agent_id)
        if not agent:
            print(f"Agent with ID '{agent_id}' not found. Available agents: {list(self.agent_manager.agents.keys())}")
            return

        # Fetch the current list of agents dynamically
        staff_list = ", ".join(
            f"{aid} ({a.params.get('role', 'Unknown Role')})"
            for aid, a in self.agent_manager.agents.items()
        )

        # Construct the system prompt dynamically
        system_prompt = (
            f"You are agent {agent.params.get('name')}, "
            f"the {agent.params.get('description', 'role description not provided')}.\n"
            f"{agent.params.get('prompt', 'act within your capacity')}.\n\n"
            f"Commands you can execute are:\n"
            f"{''.join(f'{cmd}: {info['description']} (Syntax: {info['syntax']})\n' for cmd, info in agent.COMMAND_DEFINITIONS.items())}\n"
            "Commands must start on a blank line. If you have no command, nothing will be done.\n\n"
            f"Your direct supervisor is: {agent.params.get('boss', 'None')}.\n"
            f"Your direct reports are: {', '.join(agent.subordinates) or 'None'}.\n\n"
            f"The current list of agents in this organization is: {staff_list}."
        )

        print("\n\033[36m========== AGENT DEBUG INFORMATION ==========\033[0m")
        print(f"Agent ID: {agent_id}")
        print(f"Role: {agent.params.get('role')}")
        print(f"Name: {agent.params.get('name')}")
        print(f"Boss: {agent.params.get('boss', 'None')}")
        print(f"Subordinates: {agent.subordinates or 'None'}")
        print(f"GPT Version: {agent.gpt_version}")
        print(f"State: {agent.state}")

        # Print the system prompt separately
        print("\n\033[33mSystem Prompt:\033[0m")
        print(system_prompt)

        # Print the conversation history
        print("\n\033[34mConversation History:\033[0m")
        if agent.conversation:
            for idx, msg in enumerate(agent.conversation):
                role = msg.get("role", "Unknown").capitalize()
                content = msg.get("content", "No content")
                print(f"  [{idx}] {role}: {content}")
        else:
            print("  No conversation history.")

        # Safely print pending messages from asyncio.Queue
        print("\n\033[35mPending Messages:\033[0m")
        if agent.message_queue.empty():
            print("  No pending messages.")
        else:
            print("  Messages in queue:")
            pending_messages = []
            while not agent.message_queue.empty():
                message = agent.message_queue.get_nowait()
                pending_messages.append(message)

            # Print the messages and re-queue them to preserve integrity
            for idx, message in enumerate(pending_messages):
                print(f"  [{idx}] From: {message['from']}, Message: {message['message']}")
                agent.message_queue.put_nowait(message)

        # Print task queue reference safely
        print("\n\033[32mTasks Pending or Completed:\033[0m")
        print(f"  Task Queue Reference: {repr(agent.task_queue)}")
        print("\033[36m=============================================\033[0m")

    async def run_interactive_mode(self):
        """Run the simulation in interactive mode using asynchronous input."""
        print("Entering interactive mode. Type 'help' for commands.")
        while True:
            try:
                command = await aioconsole.ainput(">> ")  # Asynchronous input
                if command == "exit":
                    print("Exiting simulation.")
                    break                               
                elif command == "help":
                    self.print_help()
                elif command == "start":
                    await self.start_simulation()
                elif command == "pause":
                    self.pause_simulation()
                elif command == "resume":
                    self.resume_simulation()
                elif command == "stop":
                    self.stop_simulation()               
                elif command.startswith("add_task"):
                    _, *task_parts = command.split(maxsplit=1)
                    task_desc = " ".join(task_parts)
                    required_agent = (await aioconsole.ainput("Assign to specific agent (leave blank if none): ")).strip() or None
                    role = (await aioconsole.ainput("Assign to role (leave blank if none): ")).strip() or None

                    # Delegate to TaskQueue
                    task = {
                        "id": len(self.task_queue.get_all_tasks()) + 1,
                        "description": task_desc,
                        "priority": "medium",
                        "required_agent": required_agent,
                        "role": role,
                    }
                    # Add the task
                    self.task_queue.add_task(task)
                elif command == "list_tasks":
                    print(self.task_queue.get_all_tasks())
                    print(self.task_queue.get_completed_tasks())
                elif command == "metrics":
                    print(self.performance_monitor.get_system_metrics())
                elif command.startswith("message_agent"):
                    if not self.agent_manager:
                        print("Simulation not started. Use 'start' command first.")
                        continue
                    try:
                        _, agent_id, *message_parts = command.split(maxsplit=2)
                        message = " ".join(message_parts)
                        if agent_id not in self.agent_manager.get_active_agents():
                            print(f"Agent {agent_id} not found.")
                        else:
                            await self.agent_manager.agents[agent_id].receive_message(
                                {"from": "User", "message": message}
                            )
                            print(f"Message sent to {agent_id}: {message}")
                    except ValueError:
                        print("Usage: message <agent_id> <message>")                      
                elif command.startswith("message_role"):
                    if not self.agent_manager:
                        print("Simulation not started. Use 'start' command first.")
                        continue
                    try:
                        _, target_role, *message_parts = command.split(maxsplit=2)
                        if not message_parts:
                            print("Usage: message_role <role_name> <message>")
                            continue

                        message = " ".join(message_parts)
                        sent_to = 0

                        # Send message to all agents matching the target role
                        for agent_id, agent in self.agent_manager.agents.items():
                            if agent.params.get("role") == target_role:
                                await agent.receive_message({"from": "User", "message": message})
                                print(f"Message sent to {agent_id} ({target_role})")
                                sent_to += 1

                        if sent_to == 0:
                            print(f"No agents found with role '{target_role}'.")
                        else:
                            print(f"Message successfully sent to {sent_to} agents with role '{target_role}'.")

                    except ValueError:
                        print("Usage: message_role <role_name> <message>")
                elif command.startswith("inject"):
                    _, agent_id, *agent_command_parts = command.split(maxsplit=2)
                    agent_command = " ".join(agent_command_parts)
                    response = await self.agent_manager.send_command_to_agent(agent_id, agent_command, {
                        "agent_manager": self.agent_manager,
                        "task_queue": self.task_queue,
                    })
                    if response:
                        print(response)
                elif command == "flush_tasks":
                    if not self.task_queue:
                        print("Simulation not started. Use 'start' command first.")
                        continue
                    self.task_queue.flush_tasks()
                    print("Task queue flushed successfully.")
                elif command.startswith("terminate_agent"):
                    if not self.agent_manager:
                        print("Simulation not started. Use 'start' command first.")
                        continue
                    try:
                        _, agent_id = command.split(maxsplit=1)
                        result = self.agent_manager.terminate_agent(agent_id)
                        print(result)
                    except ValueError:
                        print("Usage: kill_agent <agent_id>")
                elif command.startswith("agent_info"):
                    try:
                        _, agent_id = command.split(maxsplit=1)
                        if agent_id not in self.agent_manager.get_active_agents():
                            print(f"Agent {agent_id} not found.")
                        else:
                            agent = self.agent_manager.agents[agent_id]
                            info = agent.get_info()
                            print("\n\033[33m--- Agent Information ---\033[0m")
                            for key, value in info.items():
                                print(f"\033[36m{key}:\033[0m {value}")
                            print("\033[33m---------------------------\033[0m\n")
                    except ValueError:
                        print("Usage: agent_info <agent_id>")

                # Commands moved to command_processor
                elif command.startswith ("list_agents"):
                    result = await self.command_processor.process_command("list_agents", { })
                    print(result)   
                elif command.startswith ("list_roles"):
                    result = await self.command_processor.process_command("list_roles", { })
                    print(result)
                elif command.startswith ("debug_agent"):
                    result = await self.command_processor.process_command(command)
                    print(result)
                elif command.startswith ("role_info"):
                    result = await self.command_processor.process_command(command)
                    print(result)
                elif command.startswith ("spawn"):
                    result = await self.command_processor.process_command(command)
                    print(result)                      
                else:
                    print("Unknown command. Type 'help' for a list of commands.")
            except Exception as e:
                print(f"Error in interactive mode: {e}")

    def print_help(self):
        """Print the list of available commands."""
        print("""
Available Commands:
    start                    - Start the simulation
    pause                    - Pause the simulation
    resume                   - Resume the simulation
    stop                     - Stop the simulation
    spawn <role>             - Spawn a new agent with the given role
    list_agents              - List all active agents
    add_task <desc>          - Add a new task with optional metadata
    list_tasks               - List all tasks in the queue
    metrics                  - Show system performance metrics
    message_agent <agent> <msg>- Send a message to an agent
    message_role <role> <msg>- Send a message to an agent
    inject( was command) <agent> <command>- inject a command into an agent. valid commands are 'message' 'status' 'list_agents' 'broadcast'
    help                     - Show this help message
    flush_tasks              - Flush all tasks
    terminate_agent          - Terminate <agent_id>
    agent_info <agent>       - Display information about the given agent
    role_info <role>         - Display information for the given role
    list_roles               - List the configured role and the role description
    debug_agent <agent>      - Printed extended debug info for agent <agent>
    exit                     - Exit the simulation
""")

if __name__ == "__main__":
    controller = SimulationController(meta_config_file=args.meta_config)
    asyncio.run(controller.run_interactive_mode())

