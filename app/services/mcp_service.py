"""
MCP Service: Manages connections to Model Context Protocol servers.
Provides unified interface for POS, Payment, Knowledge, and Logistics servers.
"""
import logging
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class MCPService:
    """Manages MCP server connections with lazy initialization."""
    
    def __init__(self):
        self.sessions = {}
        self.exit_stack = AsyncExitStack()

    async def _connect_server(self, name: str, script_path: str):
        """Generic server connection method."""
        logger.info(f"Connecting to MCP {name} Server...")
        server_params = StdioServerParameters(
            command="python",
            args=[script_path],
            env=None
        )
        
        try:
            transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            read, write = transport
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            
            logger.info(f"Connected to {name} Server!")
            self.sessions[name.lower()] = session
            return session
        except Exception as e:
            logger.error(f"Failed to connect to {name} Server: {e}")
            return None

    async def connect_to_pos_server(self):
        return await self._connect_server("POS", "mcp-servers/pos-server/ashandy_pos_server.py")

    async def connect_to_payment_server(self):
        return await self._connect_server("Payment", "mcp-servers/payment-server/ashandy_payment_server.py")

    async def connect_to_knowledge_server(self):
        return await self._connect_server("Knowledge", "mcp-servers/knowledge-server/knowledge_server.py")

    async def connect_to_logistics_server(self):
        return await self._connect_server("Logistics", "mcp-servers/logistics-server/logistics_server.py")

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        """Call a tool on a connected MCP server with lazy connection."""
        session = self.sessions.get(server_name)
        
        if not session:
            connect_map = {
                "pos": self.connect_to_pos_server,
                "payment": self.connect_to_payment_server,
                "knowledge": self.connect_to_knowledge_server,
                "logistics": self.connect_to_logistics_server,
            }
            connector = connect_map.get(server_name)
            if connector:
                session = await connector()
            
            if not session:
                return f"Error: MCP Server '{server_name}' unavailable."

        try:
            result = await session.call_tool(tool_name, arguments=arguments)
            text_out = ""
            for content in result.content:
                if content.type == "text":
                    text_out += content.text
            return text_out
        except Exception as e:
            logger.error(f"MCP Call Error ({server_name}/{tool_name}): {e}")
            return f"Tool Execution Failed: {str(e)}"


mcp_service = MCPService()
