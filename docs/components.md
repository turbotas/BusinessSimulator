# Components Overview

This document provides a brief overview of each major component in the simulation system.

## SimulationController
- **Responsibility**: The main entry point and orchestrator. Initializes the entire system, sets up the `AgentManager`, `TaskQueue`, `CommunicationLayer`, etc.  
- **Key Methods**:
  - `initialize()`: Sets up environment, spawns initial agents.
  - `initialize_agents()`: Spawns agents according to meta-config.
  - `run_interactive_mode()`: Runs the CLI loop.

## AgentManager
- **Responsibility**: Creates and manages agents. Spawns new agents on request and handles their lifecycles (e.g., termination).  
- **Key Methods**:
  - `spawn_agent(...)`: Instantiates `BaseAgent` (or specialized agents) with the correct parameters.
  - `get_active_agents()`: Returns a list of all active agent IDs.
  - `assign_task_to_agent(...)`: Assigns tasks to an agent to be processed.

## BaseAgent
- **Responsibility**: Core agent logic. Each agent fetches tasks, processes commands, and can interact with the `CommandProcessor`, `TaskQueue`, etc.  
- **Key Methods**:
  - `perform_task(task)`: The agent’s logic to handle a given task.
  - `activity_loop()`: The main loop picking up tasks and messages.
  - `handle_command(...)`: Processes commands (e.g., "list_roles"), possibly calling the `CommandProcessor`.

## CommandProcessor
- **Responsibility**: Centralized command handling for both CLI and agent requests.  
- **Key Method**:
  - `process_command(command, simulation_context)`: Interprets commands (like `"list_roles"`) and returns or sends results.

## TaskQueue
- **Responsibility**: Stores tasks for agents to pick up.  
- **Key Methods**:
  - `add_task(task)`: Adds a new task to the queue.
  - `fetch_task_for_agent(agent_id, role)`: Returns the next suitable task for an agent.

## PerformanceMonitor
- **Responsibility**: Logs performance metrics for tasks and agents.  
- **Key Methods**:
  - `log_task_completion(agent_id, task_id, duration)`: Logs how long an agent took to complete a task.

## CommunicationLayer
- **Responsibility**: Handles messaging between agents or between external components and agents.  
- **Key Methods**:
  - `send_message(from_agent, to_agent, message)`: Queues a message for another agent.
  - `receive_message(agent_id)`: Agent fetches a message intended for it.

# Architecture Diagram

![Architecture Diagram](images/architecture_diagram.png)