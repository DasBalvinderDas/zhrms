"""ADK agent that talks to Zoho People (HR) and Zoho Payroll through Zoho's MCP server.

Setup lives in the Zoho MCP console, not in this file: create a server there,
add the "Zoho People" and "Zoho Payroll" tool groups, switch the connection to
"Authorize via Connection" (see .env.example), and copy the generated MCP URL
into ZOHO_MCP_URL. This module just wires an ADK LlmAgent to that URL as an
MCPToolset -- the concrete tool names and schemas come from Zoho at connection
time via MCP's tools/list call.
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

You support four kinds of requests:

1. Employee lookup: find an employee by name, employee ID, department, or
   designation using getEmployeeBasicDetails, and summarize their profile
   (name, email, department, designation, manager, contact). If a name is
   ambiguous, list the matches and ask which one the user means.

2. Workforce insights: report headcount and org breakdowns (by department,
   designation, location, employee type) using employeeInsights. Use
   repType to scope the query -- myReports (the current user's direct
   reports), teamReports (their whole team), or adminReports (everyone,
   admin only) -- and ask which scope is intended if it's ambiguous.

3. Leave: report leave balances/types or submit a new leave request.
   - To check balance or list leave types: fetchLeaveTypes and/or
     getLeaveBalance.
   - To apply for leave: call fetchLeaveBasicInfo first to get the
     formlinkname the applyLeave tool needs, then getLeaveBalance to confirm
     available leave types. Never take an employee ID or leave-type ID
     directly from user text -- resolve them from context. Confirm the
     employee, leave type, and date range back to the user in one sentence
     before calling applyLeave.

4. Payroll: report on pay runs. Use list_payruns to find a pay run (e.g. the
   latest, or for a given period), get_payrun for its summary, and
   list_payrun_employees / get_payrun_employee for an individual employee's
   gross pay, deductions, and net pay within that run. Always present
   amounts with their currency and the pay period they belong to.

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


def build_zoho_toolset(tool_filter=None) -> MCPToolset:
  """Creates an MCPToolset pointing at the configured Zoho MCP server.

  Pass tool_filter explicitly to override ZOHO_MCP_TOOL_FILTER from .env --
  e.g. for an admin/seed script that needs a different (and wider) set of
  tools than the conversational agent below.
  """
  return MCPToolset(
      connection_params=_connection_params(),
      tool_filter=tool_filter if tool_filter is not None else _tool_filter(),
  )


root_agent = Agent(
    name="zoho_hr_payroll_agent",
    model=os.environ.get("ADK_MODEL", "gemini-2.5-flash"),
    description="HR & payroll assistant backed by Zoho People and Zoho Payroll via MCP.",
    instruction=INSTRUCTION,
    tools=[build_zoho_toolset()],
)
