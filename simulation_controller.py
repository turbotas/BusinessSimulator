import json
import asyncio
import aioconsole
import os
import argparse
from components.agent_manager import AgentManager
from components.task_queue import TaskQueue
from components.performance_monitor import PerformanceMonitor
from components.communication_layer import CommunicationLayer
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
        self.initializing = False  # Tracks if initialization is ongoing
        self.config_file = config_file
        self.meta_config_file = meta_config_file
        self.config = self.load_config(config_file)
        self.agent_manager = None
        self.task_queue = None
        self.performance_monitor = None
        self.communication_layer = None
        self.roles_library = {}  # To store roles information
        self.initial_agents = [] # To store the list of initial agents
        self.initial_tasks = []  # To store the list of initial tasks       

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
                
                # Debugging: Print loaded sections
                print(f"Roles Library Loaded: {self.roles_library}")
                print(f"Initial Agents Loaded: {self.initial_agents}")
                print(f"Initial Tasks Loaded: {self.initial_tasks}")  # Add this debug line
                
                return meta_config
        except FileNotFoundError:
            print(f"Meta-config file not found: {self.meta_config_file}")
            return {}

    async def initialize(self):
        """Set up the simulation environment asynchronously."""
        if self.initializing:
            print("Initialization is already in progress.")
            return

        self.initializing = True
        print("Initializing simulation environment...")
        self.performance_monitor = PerformanceMonitor(self.config.get("performance_monitor", {}))
        api_key = os.getenv("OPENAI_API_KEY")
        self.task_queue = TaskQueue(self.config.get("task_queue", {}))  # Initialize task queue
        self.communication_layer = CommunicationLayer()  # Initialize communication layer
        self.agent_manager = AgentManager(
            self.config.get("agent_manager", {}),
            self.performance_monitor,
            api_key,
            self.communication_layer,
            self.task_queue  # Pass task queue to agent manager
        )

        # Load meta-config to populate roles library and initial agents
        self.load_meta_config()

        try:
            await self.initialize_agents()  # Spawn initial agents
            self.assign_initial_tasks()  # Assign tasks
            print("Simulation environment initialized.")
            self.running = True
        except Exception as e:
            print(f"Error during initialization: {e}")
        finally:
            self.initializing = False

    async def initialize_agents(self):
        """Initialize agents based on the initial_agents list in the meta-config."""
        tasks = []  # Define async tasks for agent creation
        for agent in self.initial_agents:
            role_params = self.roles_library.get(agent["role"], {})
            if not role_params:
                print(f"Role {agent['role']} not found in the role library. Skipping agent {agent['name']}.")
                continue

            agent_params = {
                "name": agent.get("name"),
                "description": role_params.get("description", "No description provided."),
                "prompt": role_params.get("prompt", ""),
                "boss": role_params.get("boss"),
                "subordinates": role_params.get("subordinates", []),
                "role": agent["role"],
                "gpt_version": role_params.get("gpt_version", self.config.get("chatgpt_agent", {}).get("default_gpt_version", "gpt-4"))
            }
            # Create an async task for each agent spawn
            tasks.append(asyncio.create_task(self.agent_manager.spawn_agent("BaseAgent", agent_params)))

        # Periodic progress reporting
        for i, task in enumerate(asyncio.as_completed(tasks), start=1):
            await task
        print(f"Initialized {i} agents...")

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
                elif command.startswith("spawn"):
                    if not self.agent_manager:
                        print("Simulation not started. Use 'start' command first.")
                        continue
                    _, agent_type, *params = command.split()
                    await self.agent_manager.spawn_agent(agent_type, {"params": params})
                elif command == "list_agents":
                    print(self.agent_manager.get_active_agents())
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
                elif command.startswith("message"):
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
                else:
                    print("Unknown command. Type 'help' for a list of commands.")
            except Exception as e:
                print(f"Error in interactive mode: {e}")

    def print_help(self):
        """Print the list of available commands."""
        print("""
Available Commands:
    start                    - Start the simulation.
    pause                    - Pause the simulation.
    resume                   - Resume the simulation.
    stop                     - Stop the simulation.
    spawn <type> <params>    - Spawn a new agent with type and optional parameters.
    list_agents              - List all active agents.
    add_task <desc>          - Add a new task with optional metadata.
    list_tasks               - List all tasks in the queue.
    metrics                  - Show system performance metrics.
    message <agent> <message>- Send a message to an agent.
    inject( was command) <agent> <command>- inject a command into an agent. valid commands are 'message' 'status' 'list_agents' 'broadcast'
    help                     - Show this help message.
    flush_tasks              - Flush all tasks.
    terminate_agent          - Terminate <agent_id>
    exit                     - Exit the simulation.
""")

if __name__ == "__main__":
    controller = SimulationController(meta_config_file=args.meta_config)
    asyncio.run(controller.run_interactive_mode())

