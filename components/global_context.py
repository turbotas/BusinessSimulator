# components/global_context.py

class GlobalContext:
    """
    A container for all globally shared references, such as
    the roles library, agent manager, and any other items
    that multiple components need easy access to.
    """
    def __init__(self, roles_library=None, agent_manager=None, task_queue=None,
                 performance_monitor=None, communication_layer=None):
        self.roles_library = roles_library
        self.agent_manager = agent_manager
        self.task_queue = task_queue
        self.performance_monitor = performance_monitor
        self.communication_layer = communication_layer
