from agents.base_agent import BaseAgent
import asyncio
from components.communication_layer import CommunicationLayer
from components.command_processor import CommandProcessor

class AgentManager:
    def __init__(self, config, performance_monitor, api_key, communication_layer, task_queue, roles_library, command_processor):
        """Initialize the agent manager."""
        self.config = config
        self.performance_monitor = performance_monitor
        self.api_key = api_key
        self.communication_layer = communication_layer  # Store communication layer reference
        self.task_queue = task_queue  # Explicitly store task queue reference
        self.agents = {}  # Dictionary to hold all active agents
        self.roles_library = roles_library  # Store the roles library
        self.command_processor = command_processor  # <-- Store the command_processor
        self.agent_tasks = {}  # Store asyncio tasks for agent activity loops
        
    async def send_command_to_agent(self, agent_id, command, simulation_context):
        """Send a command to a specific agent."""
        agent = self.agents.get(agent_id)
        if agent:
            response = await agent.handle_command(command, simulation_context)
            print(f"Agent {agent_id} response: {response}")
            return response
        else:
            print(f"Agent {agent_id} not found.")
            return None
            
    async def spawn_agent(self, agent_type, params, command_processor):
        """Spawn a new agent."""
        role_name = params.get("name", agent_type)
        agent_id = f"{role_name.replace(' ', '_')}_{len(self.agents) + 1}"

        # Debug: Spawning agent details
        #print(f"DEBUG: Spawning agent with ID {agent_id} of type {agent_type}.")
        #print(f"DEBUG: Agent params: {params}")  # Debug: Show the params passed to the agent

        # Get GPT version: use agent-specific or default
        gpt_version = params.get("gpt_version", self.config.get("chatgpt_agent", {}).get("default_gpt_version", "gpt-4o-mini"))
        #print(f"DEBUG: GPT Version for agent {agent_id}: {gpt_version}")

        # Dynamically instantiate the appropriate agent
        if agent_type == "DataAnalystAgent":
            from agents.specific_agent import DataAnalystAgent
            agent = DataAnalystAgent(agent_id, params, self.api_key, self.communication_layer, self.task_queue, gpt_version)
        else:
            # Debug: Before instantiating BaseAgent
            #print(f"DEBUG: Instantiating BaseAgent for agent ID {agent_id} with command_processor: {command_processor}")
            agent = BaseAgent(agent_id, params, self.api_key, self, self.task_queue, gpt_version, self.communication_layer, self.roles_library, command_processor)

        self.agents[agent_id] = agent

        # Start the agent's activity loop
        agent_task = asyncio.create_task(agent.activity_loop())
        self.agent_tasks[agent_id] = agent_task

        # Debug: After agent is spawned
        #print(f"DEBUG: Successfully spawned agent: {agent_id}")
        return agent_id

    def get_active_agents(self):
        """Return a list of active agent IDs."""
        return list(self.agents.keys())
        
    async def assign_task_to_agent(self, agent_id, task):
        """Assign a task to a specific agent."""
        agent = self.agents.get(agent_id)
        if agent:
            start_time = asyncio.get_event_loop().time()
            result = await agent.perform_task(task)
            end_time = asyncio.get_event_loop().time()

            # Log task completion to the performance monitor
            duration = end_time - start_time
            self.performance_monitor.log_task_completion(agent_id, task["id"], duration)

            print(f"Agent {agent_id} completed task with result: {result}")
            return result
        else:
            print(f"Agent {agent_id} not found.")
            return None
            
    def terminate_agent(self, agent_id):
        """Terminate an agent."""
        if agent_id in self.agents:
            self.agents[agent_id].stop()
            if agent_id in self.agent_tasks:
                self.agent_tasks[agent_id].cancel()
            del self.agents[agent_id]
            print(f"Terminated agent: {agent_id}")
        else:
            print(f"Agent {agent_id} not found.")

