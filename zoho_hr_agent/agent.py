"""ADK agent that talks to Zoho People (HR) and Zoho Payroll through Zoho's MCP server.

Setup lives in the Zoho MCP console (https://mcp.zoho.com), not in this file:
create a server there, add the "People" and "Payroll" tool groups, and copy
the generated MCP URL into ZOHO_MCP_URL (see .env.example). This module just
wires an ADK LlmAgent to that URL as an MCPToolset -- the concrete tool names
and schemas come from Zoho at connection time via MCP's tools/list call.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_session_manager import (
    SseConnectionParams,
    StreamableHTTPConnectionParams,
)
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

load_dotenv()

INSTRUCTION = """\
You are an HR & Payroll assistant for the company, backed by live Zoho
People and Zoho Payroll data reached through MCP tools. Only answer using
data returned by those tools -- never invent employee, leave, or pay data.

You support three kinds of requests:

1. Employee lookup: find an employee and summarize their profile (name,
   department, designation, employment status, contact info, etc.) using
   the employee/directory tools. If a name is ambiguous, list the matches
   and ask which one the user means instead of guessing.

2. Leave: report an employee's leave balance, leave history, or submit a
   new leave request using the leave-module tools. Before applying for
   leave, confirm the employee, leave type, and date range back to the
   user in one sentence, then call the tool.

3. Payroll: fetch payslips or payroll run summaries (gross pay, deductions,
   net pay, pay period) using the payroll tools. Present amounts with their
   currency and the pay period they belong to.

If a request needs a tool that isn't available on this MCP server, say so
plainly and suggest which Zoho product/tool group would need to be enabled,
rather than fabricating an answer. Keep responses concise and factual.
"""


def _connection_params():
  url = os.environ["ZOHO_MCP_URL"]
  headers = None
  api_key = os.environ.get("ZOHO_MCP_API_KEY")
  if api_key:
    headers = {"Authorization": f"Bearer {api_key}"}

  transport = os.environ.get("ZOHO_MCP_TRANSPORT", "streamable_http").lower()
  if transport == "sse":
    return SseConnectionParams(url=url, headers=headers)
  return StreamableHTTPConnectionParams(url=url, headers=headers)


def _tool_filter():
  raw = os.environ.get("ZOHO_MCP_TOOL_FILTER", "").strip()
  if not raw:
    return None
  return [name.strip() for name in raw.split(",") if name.strip()]


def build_zoho_toolset() -> MCPToolset:
  """Creates the MCPToolset pointing at the configured Zoho MCP server."""
  return MCPToolset(
      connection_params=_connection_params(),
      tool_filter=_tool_filter(),
  )


root_agent = Agent(
    name="zoho_hr_payroll_agent",
    model=os.environ.get("ADK_MODEL", "gemini-2.0-flash"),
    description="HR & payroll assistant backed by Zoho People and Zoho Payroll via MCP.",
    instruction=INSTRUCTION,
    tools=[build_zoho_toolset()],
)
