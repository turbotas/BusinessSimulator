class CommandProcessor:
    def __init__(self, global_context):
        """Initialize the command processor."""
        #self.roles_library = roles_library
        self.global_context = global_context

    async def process_command(self, command, simulation_context=None):
        """
        Centralized command processor for CLI and agent commands.
        Handles commands and returns results.
        
        If the caller is an agent (indicated by simulation_context["caller"]),
        we can also place the result into that agent's queue so it can be 'seen' or processed further.
        """
        try:
            if command.startswith ("list_roles"):
                #roles_library = simulation_context.get("roles_library", {})
                roles_library = self.global_context.roles_library
                if not roles_library:
                    return "\033[31mNo roles available in the roles library.\033[0m"
                
                # Format the roles data
                roles_list = "\n".join(
                    f"  \033[32m{role_name}\033[0m: {role_info.get('description', 'No description available.')}"
                    for role_name, role_info in roles_library.items()
                )
                
                final_output = f"\n\033[36mAvailable Roles:\033[0m\n{roles_list}\n"

                # STEP 4: If a caller is an agent, place the final_output in that agent's queue
                caller_id = simulation_context.get("caller")  # Could be "CEO_1", "CTO_2", etc.
                agent_manager = simulation_context.get("agent_manager")
                
                # Debug line: see if we even get here
                print(f"DEBUG: list_roles command recognized. caller={caller_id}, agent_manager={agent_manager}")
              
                # If the caller is an agent in our system, we queue a new 'task' with the command output
                if caller_id and agent_manager and caller_id in agent_manager.agents:
                    target_agent = agent_manager.agents[caller_id]
                    
                    # Create a new 'task' with the result
                    new_task = {
                        "id": f"list_roles_result-{len(target_agent.message_queue._queue)+1}",
                        "description": f"Command Output (list_roles):\n{final_output}",
                        "priority": "medium",
                    }
                    # Put it in that agent's queue so the agent can read it in activity_loop
                    target_agent.message_queue.put_nowait(new_task)
                
                # Return the final_output so the caller (CLI or agent) can also see it
                return final_output
            elif command.startswith ("list_agents"):
                # We'll fetch the AgentManager from the global context
                agent_manager = self.global_context.agent_manager
                if not agent_manager:
                    return "\033[31mNo agent manager available.\033[0m"

                active_ids = agent_manager.get_active_agents()
                if not active_ids:
                    final_output = "\033[31mNo active agents in the simulation.\033[0m"
                else:
                    # Build a formatted list of agent IDs + roles
                    lines = []
                    for agent_id in active_ids:
                        agent = agent_manager.agents.get(agent_id)
                        role = agent.params.get("role", "Unknown Role") if agent else "Unknown Role"
                        lines.append(f"  \033[32m{agent_id}\033[0m: {role}")
                    final_output = "\n\033[36mActive Agents:\033[0m\n" + "\n".join(lines) + "\n"

                # If the caller is an agent, queue the output back to the agent
                caller_id = simulation_context.get("caller")
                print(f"DEBUG: list_agents command recognized. caller={caller_id}, agent_manager={agent_manager}")

                if caller_id and agent_manager and caller_id in agent_manager.agents:
                    target_agent = agent_manager.agents[caller_id]
                    new_task = {
                        "id": f"list_agents_result-{len(target_agent.message_queue._queue) + 1}",
                        "description": f"Command Output (list_agents):\n{final_output}",
                        "priority": "medium",
                    }
                    target_agent.message_queue.put_nowait(new_task)

                return final_output
            elif command.startswith("debug_agent"):
                # Note - this command can be run by an agentt but does NOT give the agent the output or schedule a new  task for them.
                
                # 1) Parse out the agent ID from the command, e.g. "debug_agent CEO_1"
                tokens = command.split(maxsplit=1)
                if len(tokens) < 2:
                    return "Usage: debug_agent <agent_id>"
                agent_id = tokens[1].strip()

                # 2) Access the global context's agent_manager
                agent_manager = self.global_context.agent_manager
                if not agent_manager:
                    return "No agent manager available to debug an agent."

                # 3) Check if this agent exists
                if agent_id not in agent_manager.agents:
                    return f"Agent '{agent_id}' not found. Available agents: {list(agent_manager.agents.keys())}"

                # 4) Fetch the agent and build a debug output string
                agent = agent_manager.agents[agent_id]
                info_lines = []

                info_lines.append("\n\033[36m========== AGENT DEBUG INFORMATION ==========\033[0m")
                info_lines.append(f"Agent ID: {agent_id}")
                role = agent.params.get("role", "Unknown")
                info_lines.append(f"Role: {role}")
                name = agent.params.get("name", "No name provided")
                info_lines.append(f"Name: {name}")
                boss = agent.params.get("boss", "None")
                info_lines.append(f"Boss: {boss}")
                subs = agent.subordinates or []
                info_lines.append(f"Subordinates: {subs if subs else 'None'}")
                info_lines.append(f"GPT Version: {agent.gpt_version}")
                info_lines.append(f"State: {agent.state}")

                # 5) Conversation history
                info_lines.append("\n\033[34mConversation History:\033[0m")
                if agent.conversation:
                    for idx, msg in enumerate(agent.conversation):
                        role_label = msg.get("role", "Unknown").capitalize()
                        content = msg.get("content", "No content")
                        info_lines.append(f"  [{idx}] {role_label}: {content}")
                else:
                    info_lines.append("  No conversation history.")

                # 6) Pending messages
                info_lines.append("\n\033[35mPending Messages:\033[0m")
                if agent.message_queue.empty():
                    info_lines.append("  No pending messages.")
                else:
                    pending_messages = []
                    while not agent.message_queue.empty():
                        message = agent.message_queue.get_nowait()
                        pending_messages.append(message)

                    info_lines.append("  Messages in queue:")
                    for idx, message in enumerate(pending_messages):
                        from_whom = message.get("from", "Unknown")
                        text = message.get("message", "No message content")
                        info_lines.append(f"  [{idx}] From: {from_whom}, Message: {text}")
                        # Re-queue them to preserve state
                        agent.message_queue.put_nowait(message)

                # 7) Task queue reference
                info_lines.append("\n\033[32mTasks Pending or Completed:\033[0m")
                info_lines.append(f"  Task Queue Reference: {repr(agent.task_queue)}")
                info_lines.append("\033[36m=============================================\033[0m")

                # 8) Join everything into one final string
                final_output = "\n".join(str(line) for line in info_lines)
                return final_output
            elif command.startswith("role_info"):
                # 1) Parse out the requested role name, e.g. "role_info CTO"
                tokens = command.split(maxsplit=1)
                if len(tokens) < 2:
                    return "Usage: role_info <role>"

                role_name = tokens[1].strip()

                # 2) Fetch the global roles_library
                roles_library = self.global_context.roles_library
                if not roles_library:
                    return "\033[31mNo roles library available.\033[0m"

                # 3) Check if the role exists
                if role_name not in roles_library:
                    role_list_str = ", ".join(roles_library.keys()) if roles_library else "None"
                    return (f"Error: Role '{role_name}' not found in the roles library.\n"
                            f"Available roles: {role_list_str}")

                # 4) Build the text for role info
                role_data = roles_library[role_name]
                lines = []
                lines.append("\n\033[36mRole Information:\033[0m")
                lines.append(f"  \033[32mRole:\033[0m {role_name}")
                lines.append(f"  \033[32mDescription:\033[0m {role_data.get('description', 'No description available.')}")
                lines.append(f"  \033[32mPrompt:\033[0m {role_data.get('prompt', 'No prompt available.')}")
                lines.append(f"  \033[32mBoss:\033[0m {role_data.get('boss', 'None')}")
                subs = role_data.get('subordinates', [])
                lines.append(f"  \033[32mSubordinates:\033[0m {', '.join(subs) or 'None'}")
                lines.append(f"  \033[32mGPT Version:\033[0m {role_data.get('gpt_version', 'Default')}")
                lines.append(f"  \033[32mMinimum Count:\033[0m {role_data.get('min_count', 0)}")
                lines.append(f"  \033[32mMaximum Count:\033[0m {role_data.get('max_count', 'Unlimited')}")

                final_output = "\n".join(lines) + "\n"

                # 5) Optionally, if the caller is an agent, queue the result as a new task
                caller_id = simulation_context.get("caller") if simulation_context else None
                agent_manager = self.global_context.agent_manager
                if caller_id and agent_manager and caller_id in agent_manager.agents:
                    target_agent = agent_manager.agents[caller_id]
                    new_task = {
                        "id": f"role_info_result-{len(target_agent.message_queue._queue)+1}",
                        "description": f"Command Output (role_info {role_name}):\n{final_output}",
                        "priority": "medium",
                    }
                    target_agent.message_queue.put_nowait(new_task)

                # 6) Return the final output
                return final_output
            elif command.startswith("spawn"):
                """
                Command: spawn <role>
                Example: spawn CFO
                Spawns a new agent with the given role, if that role is defined in the roles library.
                This version is fully async, and also pushes the result back to the caller if it's an agent.
                """
                tokens = command.split(maxsplit=1)
                if len(tokens) < 2:
                    return "Usage: spawn <role>"

                role_name = tokens[1].strip()

                # 1) Fetch roles library from global context
                roles_library = self.global_context.roles_library
                if not roles_library:
                    return "Error: No roles library loaded; cannot spawn agents."

                # 2) Validate the role
                if role_name not in roles_library:
                    available_roles = ", ".join(roles_library.keys()) if roles_library else "None"
                    return (
                        f"Error: Role '{role_name}' is not defined in the roles library.\n"
                        f"Available roles: {available_roles}"
                    )

                # 3) Build agent parameters from the role definition
                role_params = roles_library[role_name]
                agent_name = f"{role_name}"
                agent_params = {
                    "name": agent_name,
                    "description": role_params.get("description", "No description provided."),
                    "prompt": role_params.get("prompt", ""),
                    "boss": role_params.get("boss"),
                    "subordinates": role_params.get("subordinates", []),
                    "role": role_name,
                    "gpt_version": role_params.get("gpt_version", "gpt-4o"),
                }

                # 4) Access the AgentManager from global context
                agent_manager = self.global_context.agent_manager
                if not agent_manager:
                    return "Error: AgentManager is not available; cannot spawn agents."

                # 5) Actually spawn the agent (asynchronously)
                try:
                    # Because process_command is presumably called in an async context,
                    # we can just await spawn_agent instead of using asyncio.run.
                    agent_id = await agent_manager.spawn_agent(role_name, agent_params, self)
                except Exception as e:
                    return f"Error spawning agent of role '{role_name}': {str(e)}"

                final_output = f"Successfully spawned agent '{agent_id}' with role '{role_name}'."

                # 6) If caller is an agent, queue the result as a new “task”
                caller_id = simulation_context.get("caller") if simulation_context else None
                if caller_id and agent_manager and caller_id in agent_manager.agents:
                    target_agent = agent_manager.agents[caller_id]
                    new_task = {
                        "id": f"spawn_result-{len(target_agent.message_queue._queue)+1}",
                        "description": f"Command Output (spawn {role_name}):\n{final_output}",
                        "priority": "medium",
                    }
                    target_agent.message_queue.put_nowait(new_task)

                # 7) Return final output so the CLI or calling agent sees it immediately
                return final_output


            else:
                return f"\033[31mUnknown command: {command}\033[0m"

        except Exception as e:
            return f"\033[31mError processing command: {str(e)}\033[0m"
