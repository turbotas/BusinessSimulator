class CommandProcessor:
    def __init__(self, roles_library):
        """Initialize the command processor."""
        self.roles_library = roles_library

    def process_command(self, command, simulation_context):
        """
        Centralized command processor for CLI and agent commands.
        Handles commands and returns results.
        """
        try:
            if command == "list_roles":
                roles_library = simulation_context.get("roles_library", {})
                if not roles_library:
                    return "\033[31mNo roles available in the roles library.\033[0m"
                
                # Add pretty formatting with colors and headers
                roles_list = "\n".join(
                    f"  \033[32m{role_name}\033[0m {role_info.get('description', 'No description available.')}"
                    for role_name, role_info in roles_library.items()
                )
                
                return f"\n\033[36mAvailable Roles:\033[0m\n{roles_list}\n"
            else:
                return f"\033[31mUnknown command: {command}\033[0m"
        except Exception as e:
            return f"\033[31mError processing command: {str(e)}\033[0m"
