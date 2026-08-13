"""Diagnostic: call one Zoho MCP tool directly (bypassing the LLM entirely)
and print its full, untruncated response. Useful when the agent's own
summary of a tool result is unclear or wrong, and you need to see exactly
what Zoho actually returned.

    python scripts/call_tool.py ZohoCreator_getFormMetadata \\
      '{"path_variables": {"account_owner_name": "your-owner", "app_link_name": "human-resource-management", "form_link_name": "Salary_Structure"}}'

Tool name and argument shape must match what discover_tools.py shows for
that tool (it prints each tool's description, which documents its
path_variables/query_params/body). No agent, no model, no tool_filter --
just a direct MCP session call.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client


async def main() -> None:
  if len(sys.argv) < 2:
    print("Usage: python scripts/call_tool.py <tool_name> ['<json_args>']")
    raise SystemExit(1)

  tool_name = sys.argv[1]
  args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

  url = os.environ["ZOHO_MCP_URL"]
  transport = os.environ.get("ZOHO_MCP_TRANSPORT", "streamable_http").lower()
  client_cm = sse_client(url) if transport == "sse" else streamablehttp_client(url)

  async with client_cm as streams:
    read, write = streams[0], streams[1]
    async with ClientSession(read, write) as session:
      await session.initialize()
      result = await session.call_tool(tool_name, args)
      for item in result.content:
        text = getattr(item, "text", None)
        if text is None:
          print(item)
          continue
        try:
          print(json.dumps(json.loads(text), indent=2))
        except json.JSONDecodeError:
          print(text)


if __name__ == "__main__":
  asyncio.run(main())
