class CommandProcessor:
    def __init__(self, global_context):
        """Initialize the command processor."""
        #self.roles_library = roles_library
        self.global_context = global_context

    def process_command(self, command, simulation_context=None):
        """
        Centralized command processor for CLI and agent commands.
        Handles commands and returns results.
        
        If the caller is an agent (indicated by simulation_context["caller"]),
        we can also place the result into that agent's queue so it can be 'seen' or processed further.
        """
        try:
            if command == "list_roles":
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

            else:
                return f"\033[31mUnknown command: {command}\033[0m"

        except Exception as e:
            return f"\033[31mError processing command: {str(e)}\033[0m"
