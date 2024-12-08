import asyncio

class CommunicationLayer:
    def __init__(self):
        """Initialize the communication layer."""
        self.message_queues = {}

    def get_message_queue(self, agent_id):
        """Get or create a message queue for an agent."""
        if agent_id not in self.message_queues:
            self.message_queues[agent_id] = asyncio.Queue()
        return self.message_queues[agent_id]

    async def send_message(self, from_agent, to_agent, message):
        """Send a message from one agent to another."""
        queue = self.get_message_queue(to_agent)
        await queue.put({"from": from_agent, "message": message})
        print(f"Message sent from {from_agent} to {to_agent}: {message}")

    async def receive_message(self, agent_id):
        """Receive a message for an agent."""
        queue = self.get_message_queue(agent_id)
        message = await queue.get()
        print(f"Message received by {agent_id}: {message}")
        return message

