"""Start a real SDK server process and compare local and MCP tool results."""
import asyncio
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from practice.enterprise_ai.policy_agent import lookup_limit
from practice.integration_labs.mcp_server import TENANT, policies


async def run() -> dict:
    params = StdioServerParameters(command=sys.executable,
                                  args=["-m", "practice.integration_labs.mcp_server"],
                                  cwd=str(Path(__file__).resolve().parents[2]))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            expected = lookup_limit(policies(), TENANT, "2026-10-01")
            result = await session.call_tool("get_prepayment_limit", {"request": {"as_of": "2026-10-01"}})
            if result.isError or result.structuredContent != expected:
                raise ValueError("Local/MCP contract mismatch")
            source = await session.call_tool("get_policy_source", {
                "request": {"as_of": "2026-10-01", "source_id": expected["source_id"]}})
            if source.isError or source.structuredContent["source_id"] != expected["source_id"]:
                raise ValueError("Missing policy evidence")
            injection = await session.call_tool("get_prepayment_limit", {
                "request": {"as_of": "2026-10-01", "tenant_id": "tenant-b"}})
            hidden = await session.call_tool("get_policy_source", {
                "request": {"as_of": "2026-10-01", "source_id": "policy-b-current"}})
            if not injection.isError or not hidden.isError:
                raise ValueError("Identity or source boundary failed")
            return {"tools": [tool.name for tool in tools.tools], "result": result.structuredContent,
                    "local_equal": True, "identity_injection_rejected": True, "other_tenant_hidden": True}


async def main():
    async with asyncio.timeout(20):
        print(json.dumps(await run(), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
