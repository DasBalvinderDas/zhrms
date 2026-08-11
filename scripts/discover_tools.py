"""Sanity check: connect to the Zoho MCP server and print what it exposes.

Run this first, before touching the agent, to confirm ZOHO_MCP_URL / auth are
correct and to see the actual tool names Zoho gives you (they depend on which
tool groups you enabled for this server in the Zoho MCP console).

    python scripts/discover_tools.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zoho_hr_agent.agent import build_zoho_toolset


async def main() -> None:
  toolset = build_zoho_toolset()
  try:
    tools = await toolset.get_tools()
    if not tools:
      print("Connected, but no tools were returned. Check that tool groups "
            "are enabled on the Zoho MCP server and any ZOHO_MCP_TOOL_FILTER "
            "matches real tool names.")
      return
    print(f"Zoho MCP server exposes {len(tools)} tool(s):\n")
    for tool in tools:
      description = (tool.description or "").strip().splitlines()[0] if tool.description else ""
      print(f"- {tool.name}: {description}")
  finally:
    await toolset.close()


if __name__ == "__main__":
  asyncio.run(main())
