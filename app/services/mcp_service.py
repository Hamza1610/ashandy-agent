import logging
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

class MCPService:
    def __init__(self):
        self.sessions = {}
        self.exit_stack = AsyncExitStack()

    async def connect_to_pos_server(self):
        """
        Connect to the local POS MCP Server using stdio.
        """
        logger.info("Connecting to MCP POS Server...")
        server_params = StdioServerParameters(
            command="python",
            args=["mcp-servers/pos-server/ashandy_pos_server.py"], # Adjust path relative to CWD
            env=None # Inherit env (e.g. .env vars)
        )
        
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.read, self.write = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(self.read, self.write))
            await session.initialize()
            
            logger.info("Connected to POS Server!")
            self.sessions["pos"] = session
            return session
        except Exception as e:
            logger.error(f"Failed to connect to POS Server: {e}")
            return None

    async def connect_to_payment_server(self):
        """
        Connect to the local Payment MCP Server using stdio.
        """
        logger.info("Connecting to MCP Payment Server...")
        server_params = StdioServerParameters(
            command="python",
            args=["mcp-servers/payment-server/ashandy_payment_server.py"],
            env=None
        )
        
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.read_pay, self.write_pay = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(self.read_pay, self.write_pay))
            await session.initialize()
            
            logger.info("Connected to Payment Server!")
            self.sessions["payment"] = session
            return session
        except Exception as e:
            logger.error(f"Failed to connect to Payment Server: {e}")
            return None

    async def connect_to_knowledge_server(self):
        """
        Connect to the local Knowledge MCP Server.
        """
        logger.info("Connecting to MCP Knowledge Server...")
        server_params = StdioServerParameters(
            command="python",
            args=["mcp-servers/knowledge-server/knowledge_server.py"],
            env=None
        )
        try:
            # We use a separate context for knowledge server
            # Note: For production, we might want to consolidate context management
            transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            read, write = transport
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            
            logger.info("Connected to Knowledge Server!")
            self.sessions["knowledge"] = session
            return session
        except Exception as e:
            logger.error(f"Failed to connect to Knowledge Server: {e}")
            return None

    async def connect_to_logistics_server(self):
        """
        Connect to the local Logistics MCP Server.
        """
        logger.info("Connecting to MCP Logistics Server...")
        server_params = StdioServerParameters(
            command="python",
            args=["mcp-servers/logistics-server/logistics_server.py"],
            env=None
        )
        try:
            transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            read, write = transport
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            
            logger.info("Connected to Logistics Server!")
            self.sessions["logistics"] = session
            return session
        except Exception as e:
            logger.error(f"Failed to connect to Logistics Server: {e}")
            return None

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        """
        Call a tool on a connected MCP server.
        """
        session = self.sessions.get(server_name)
        if not session:
            # Lazy connect
            if server_name == "pos":
                session = await self.connect_to_pos_server()
            elif server_name == "payment":
                session = await self.connect_to_payment_server()
            elif server_name == "knowledge":
                session = await self.connect_to_knowledge_server()
            elif server_name == "logistics":
                session = await self.connect_to_logistics_server()
            
            if not session:
                return f"Error: MCP Server '{server_name}' unavailable."

        try:
            result = await session.call_tool(tool_name, arguments=arguments)
            # Result is a list of content blocks (TextContent, ImageContent)
            # We extract text
            text_out = ""
            for content in result.content:
                if content.type == "text":
                    text_out += content.text
            return text_out
        except Exception as e:
            logger.error(f"MCP Call Error ({server_name}/{tool_name}): {e}")
            return f"Tool Execution Failed: {str(e)}"

# Singleton
mcp_service = MCPService()
