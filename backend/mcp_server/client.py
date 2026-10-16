"""MCP client used by the agent orchestrator.

Calls the tools exposed by mcp_server/server.py through a real MCP
ClientSession (SSE transport), so the agent loop genuinely speaks MCP.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

MCP_URL = os.getenv("MCP_URL", "http://localhost:8001/sse")


async def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke an MCP tool by name and return the parsed JSON payload."""
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    # The MCP server is always localhost: strip proxy env vars so httpx does
    # not try to route (or misparse NO_PROXY entries for) the local connection.
    import os

    proxy_keys = [k for k in os.environ if k.lower().endswith("_proxy")]
    saved = {k: os.environ.pop(k) for k in proxy_keys}
    try:
        async with sse_client(MCP_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
    finally:
        os.environ.update(saved)
    # FastMCP returns a list of content blocks; the first text block is JSON.
    text = ""
    for block in result.content:
        if getattr(block, "type", "") == "text":
            text = block.text
            break
    try:
        return json.loads(text) if text else {"raw": text}
    except json.JSONDecodeError:
        return {"raw": text}
