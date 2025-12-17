"""
MCP Service: Manages connections to Model Context Protocol servers.
Provides unified interface for POS, Payment, Knowledge, and Logistics servers.
"""
import logging
from contextlib import AsyncExitStack
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import asyncio

logger = logging.getLogger(__name__)


class MCPService:
    """Manages MCP server connections with lazy initialization."""
    
    def __init__(self):
        self.sessions = {}
        self.exit_stack = AsyncExitStack()
        # Locks to prevent concurrent connection attempts (Gap 6 Fix)
        self._locks = {
            "pos": asyncio.Lock(),
            "payment": asyncio.Lock(),
            "knowledge": asyncio.Lock(),
            "logistics": asyncio.Lock()
        }

    async def _connect_server(self, name: str, script_path: str):
        """Generic server connection method."""
        import os
        logger.info(f"Connecting to MCP {name} Server...")
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[script_path],
            env=os.environ.copy()  # CRITICAL: Pass env vars to subprocess!
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

    async def initialize_all(self):
        """
        Connect to all defined MCP servers.
        
        Must be called during application startup (lifespan) to ensure
        anyio TaskGroups are created in the main event loop, preventing
        'RuntimeError: Attempted to exit cancel scope in a different task'
        during shutdown.
        """
        logger.info("Initializing MCP Server connections...")
        # Concurrent initialization
        await asyncio.gather(
            self.connect_to_pos_server(),
            self.connect_to_payment_server(),
            self.connect_to_knowledge_server(),
            self.connect_to_logistics_server(),
            return_exceptions=True
        )
        logger.info("MCP Server initialization complete.")

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        """Call a tool on a connected MCP server."""
        lock = self._locks.get(server_name)
        if not lock:
             return f"Error: Unknown server '{server_name}'."

        async with lock:
            session = self.sessions.get(server_name)
            
            if not session:
                return f"Error: MCP Server '{server_name}' is not connected. Check startup logs."

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

    async def get_health_status(self) -> dict:
        """
        Get health status of all MCP servers.
        
        Returns dict with server names as keys and status info as values.
        Used for /health endpoint and monitoring.
        """
        status = {}
        server_names = ["pos", "payment", "knowledge", "logistics"]
        
        for name in server_names:
            session = self.sessions.get(name)
            if session:
                # Try a simple ping-like check
                try:
                    # Just check if session exists and is connected
                    status[name] = {
                        "status": "connected",
                        "session_id": id(session)
                    }
                except Exception as e:
                    status[name] = {
                        "status": "error",
                        "error": str(e)
                    }
            else:
                status[name] = {
                    "status": "disconnected",
                    "error": "Session not initialized"
                }
        
        return status

    async def cleanup(self):
        """Clean up resources and close connections."""
        logger.info("Cleaning up MCP connections...")
        try:
            # anyio's TaskGroup is strict about running open/close in the same task.
            # FastAPI lifespan sometimes switches tasks between startup/shutdown.
            # We catch this specific error to avoid noisy stack traces on exit.
            await self.exit_stack.aclose()
            self.sessions.clear()
        except RuntimeError as e:
            if "exit cancel scope" in str(e):
                logger.debug(f"Suppressing expected shutdown task error: {e}")
            else:
                logger.error(f"Error cleaning up MCP connections: {e}")
        except Exception as e:
            logger.error(f"Error cleaning up MCP connections: {e}")


mcp_service = MCPService()
