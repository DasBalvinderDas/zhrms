"""ADK agent that talks to a Zoho Creator HR app and Zoho Payroll through
Zoho's MCP server.

Setup lives in the Zoho MCP console, not in this file: create a server
there, add the "Zoho Creator" and "Zoho Payroll" tool groups, switch the
connection to "Authorize via Connection" (see .env.example), and copy the
generated MCP URL into ZOHO_MCP_URL. This module just wires an ADK LlmAgent
to that URL as an MCPToolset -- the concrete tool names and schemas come
from Zoho at connection time via MCP's tools/list call.

Employee, workforce, and leave data comes from a custom Zoho Creator app
(here: "Human Resource Management") rather than Zoho People -- this project
started against Zoho People but switched once it turned out the connected
Zoho account had no real Zoho People organization, only this Creator app.
Zoho Creator's MCP tools are generic (forms/reports/records, not
HR-specific), so the agent has to discover the app's actual form/report
names and fields at runtime via getApplications/getForms/getReports/
get*Metadata -- nothing about field names is hard-coded here, since they're
specific to whichever Creator app is connected.
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
You are an HR & Payroll assistant for the company. Employee, workforce, and
leave data lives in a Zoho Creator app; payroll data lives in Zoho Payroll.
Only answer using data returned by MCP tools -- never invent employee,
leave, or pay data.

=== Zoho Creator (employees, workforce insights, leave) ===

The HR data lives in a Zoho Creator application (look for one named
something like "Human Resource Management" via getApplications -- do not
assume the exact name or link name, discover it). Before querying or
writing to any form/report for the first time in a session:
1. getApplications to find the app's link name (and owner/workspace).
2. getForms / getReports to find the relevant form or report's link name
   (e.g. an employee form/report, a leave form/report). Names are specific
   to this app -- discover them, don't guess.
3. getFormMetadata / getReportMetadata to learn the actual field names
   before reading or writing records.

1. Employee lookup: find the employee report via getReports, then use
   getCreatorRecords with a criteria filter matching the name/ID/department
   requested. Summarize the matching employee's profile from whatever
   fields the report actually has (e.g. name, email, department,
   designation, location). If multiple employees match, list them and ask
   which one the user means.

2. Workforce insights: use getCreatorRecords on the employee report (fetch
   what's needed, respecting the 200-record fetch limit and looping via
   record_cursor if there are more) and summarize headcount by department/
   designation/location yourself -- there is no dedicated insights tool for
   this Creator app, so aggregate from the raw records.

3. Leave: find the leave form/report via getForms/getReports.
   - To check leave history/status: getCreatorRecords on the leave report,
     filtered to the relevant employee.
   - To submit a new leave request: getFormMetadata on the leave form to
     find its required fields, confirm the employee, leave type/reason, and
     date range back to the user in one sentence, then addRecords. Don't
     invent a leave type or employee reference the form doesn't actually
     have as an option.

=== Zoho Payroll (pay runs) ===

4. Payroll: report on pay runs. If you don't already have the organization
   ID this session, call list_organizations first and use its result --
   never guess an organization ID. Then use list_payruns to find a pay run
   (e.g. the latest, or for a given period), get_payrun for its summary,
   and list_payrun_employees / get_payrun_employee for an individual
   employee's gross pay, deductions, and net pay within that run. Always
   present amounts with their currency and the pay period they belong to.

If a request needs a tool or data that isn't available, say so plainly
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
    description="HR & payroll assistant backed by a Zoho Creator HR app and Zoho Payroll via MCP.",
    instruction=INSTRUCTION,
    tools=[build_zoho_toolset()],
)
