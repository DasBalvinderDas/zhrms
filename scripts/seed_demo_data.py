"""One-time admin script: seeds demo departments, employees, and leave types
into a fresh Zoho People organization via Zoho MCP form tools, so the demo
use cases in scripts/run_demo.py have real data to query.

    python scripts/seed_demo_data.py

Uses a separate, wider set of Zoho MCP tools than the conversational agent
(zoho_hr_agent.agent.root_agent) -- generic form/record CRUD tools that
create data, which the day-to-day HR/payroll assistant intentionally does
not have access to. It's driven by an LLM (not hardcoded field names)
because the Employee/Department forms' exact fields and lookup options are
account-specific and only discoverable at runtime via identifyForm/getFields.

Not covered: Zoho Payroll employee records and salary structures. Nothing in
the currently available Payroll tool set can create those (only fetch/report
tools exist for compensation) -- that setup has to happen once in the
Payroll web UI (payroll.zoho.in) before payroll pay-run tools will return
real data.

Safe to re-run: the agent is instructed to check for existing records first
and skip anything already there.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

from zoho_hr_agent.agent import build_zoho_toolset

SEED_TOOL_FILTER = [
    "ZohoPeople_identifyForm",
    "ZohoPeople_getFields",
    "ZohoPeople_getFieldOptions",
    "ZohoPeople_getLookupOptions",
    "ZohoPeople_getRecords",
    "ZohoPeople_addRecord",
    "ZohoPeople_getEmployeeBasicDetails",
    "ZohoPeople_getDepartmentDetails",
    "ZohoPeople_fetchLeaveTypes",
    "ZohoPeople_addLeaveType",
]

SEED_INSTRUCTION = """\
You are a one-time setup assistant for a fresh Zoho People organization.
Create the demo data listed below, using the form tools (identifyForm,
getFields, getFieldOptions, getLookupOptions, addRecord, getRecords) for
departments and employees, and addLeaveType for leave types.

Before creating anything, check what already exists (getRecords /
getEmployeeBasicDetails for employees and departments, fetchLeaveTypes for
leave types) and skip anything that's already there -- do not create
duplicates.

Departments to ensure exist (create via the Department system form if
missing):
- Engineering
- Human Resources

Employees to ensure exist (create via the Employee system form if missing;
resolve each employee's Department field to the departments above via that
field's lookup options):
- Asha Verma, asha.verma@demo-coe-org.example, Engineering, Software Engineer
- Rahul Nair, rahul.nair@demo-coe-org.example, Engineering, Engineering Manager
- Priya Shah, priya.shah@demo-coe-org.example, Human Resources, HR Executive

Leave types to ensure exist (create via addLeaveType if missing, applicable
to everyone -- for every key in 'applicable' [Departments, Designations,
Locations, Roles, Users, Genders, MaritalStatus] use mode '1', list ['-1']):
- Casual Leave, code CAS, PAID, unit DAY
- Sick Leave, code SIC, PAID, unit DAY

Work through these one at a time. After each creation attempt, state
plainly whether it succeeded, already existed, or failed (with the error).
Finish with a short summary table of created vs. already-existed vs. failed.
"""


async def main() -> None:
  agent = Agent(
      name="zoho_seed_agent",
      model=os.environ.get("ADK_MODEL", "gemini-2.5-flash"),
      description="One-time admin agent that seeds demo Zoho People data.",
      instruction=SEED_INSTRUCTION,
      tools=[build_zoho_toolset(tool_filter=SEED_TOOL_FILTER)],
  )

  runner = InMemoryRunner(agent=agent, app_name="zoho_hr_seed")
  user_id, session_id = "seed-admin", str(uuid.uuid4())
  await runner.session_service.create_session(
      app_name="zoho_hr_seed", user_id=user_id, session_id=session_id
  )

  prompt = "Set up the demo departments, employees, and leave types as instructed."

  try:
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
      if event.is_final_response() and event.content and event.content.parts:
        text = "".join(p.text or "" for p in event.content.parts)
        if text:
          print(text.strip())
  finally:
    await runner.close()


if __name__ == "__main__":
  asyncio.run(main())
