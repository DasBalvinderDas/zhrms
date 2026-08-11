"""One-time admin script: seeds demo departments, employees, and leave types
into a fresh Zoho People + Zoho Payroll organization via Zoho MCP tools, so
the demo use cases in scripts/run_demo.py have real data to query.

    python scripts/seed_demo_data.py

Uses a separate, wider set of Zoho MCP tools than the conversational agent
(zoho_hr_agent.agent.root_agent) -- tools that create/modify data, which the
day-to-day HR/payroll assistant intentionally does not have access to.

Zoho People employees are created through its generic form mechanism
(identifyForm/getFields/getFieldOptions/getLookupOptions/addRecord) because
the Employee form's exact fields and lookup options are account-specific and
only discoverable at runtime. Zoho Payroll has its own dedicated
create_department/create_designation/create_work_location/create_employee
tools instead -- Payroll keeps a separate employee/org-structure record from
People, so both sides need seeding independently.

Not covered: Payroll salary assignment and pay run creation. Nothing in the
currently available Payroll tool set can set an employee's base salary
(only fetch/list tools exist for salary templates and components) -- that
still has to happen once in the Payroll web UI (payroll.zoho.in) before a
pay run will have real numbers in it.

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
    # Zoho People: generic form CRUD, used for Department + Employee records.
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
    # Zoho Payroll: dedicated org-structure + employee tools.
    "ZohoPayroll_list_departments",
    "ZohoPayroll_create_department",
    "ZohoPayroll_list_designations",
    "ZohoPayroll_create_designation",
    "ZohoPayroll_list_work_locations",
    "ZohoPayroll_create_work_location",
    "ZohoPayroll_list_employees",
    "ZohoPayroll_get_employee",
    "ZohoPayroll_create_employee",
]

SEED_INSTRUCTION = """\
You are a one-time setup assistant for a fresh Zoho People + Zoho Payroll
organization. Create the demo data listed below. Zoho People and Zoho
Payroll keep separate employee records -- set up both sides.

Before creating anything, check what already exists (getRecords /
getEmployeeBasicDetails for People employees and departments,
fetchLeaveTypes for leave types, list_departments / list_designations /
list_work_locations / list_employees for Payroll) and skip anything that's
already there -- do not create duplicates.

=== Zoho People ===

Departments to ensure exist (create via the Department system form --
identifyForm, getFields, addRecord -- if missing):
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

=== Zoho Payroll ===

Departments to ensure exist (create_department if missing):
- Engineering
- Human Resources

Designations to ensure exist (create_designation if missing):
- Software Engineer
- Engineering Manager
- HR Executive

One work location to ensure exists (create_work_location if missing) --
use the organization's own address if the tool needs one, otherwise a
reasonable default name like "Head Office".

Employees to ensure exist (create_employee if missing, using the same three
people as above, referencing the Payroll department/designation/work
location records you just ensured exist -- read create_employee's own
parameter schema for exactly which fields it requires, and use sensible
values for anything mandatory that isn't specified here, e.g. a date of
joining of today):
- Asha Verma, asha.verma@demo-coe-org.example, Engineering, Software Engineer
- Rahul Nair, rahul.nair@demo-coe-org.example, Engineering, Engineering Manager
- Priya Shah, priya.shah@demo-coe-org.example, Human Resources, HR Executive

Do NOT attempt to assign salaries or create a pay run -- no available tool
can set an employee's salary, so leave that for manual setup.

Work through all of this one item at a time. After each creation attempt,
state plainly whether it succeeded, already existed, or failed (with the
error). Finish with a short summary table of created vs. already-existed
vs. failed, split by Zoho People vs. Zoho Payroll.
"""


async def main() -> None:
  agent = Agent(
      name="zoho_seed_agent",
      model=os.environ.get("ADK_MODEL", "gemini-2.5-flash"),
      description="One-time admin agent that seeds demo Zoho People/Payroll data.",
      instruction=SEED_INSTRUCTION,
      tools=[build_zoho_toolset(tool_filter=SEED_TOOL_FILTER)],
  )

  runner = InMemoryRunner(agent=agent, app_name="zoho_hr_seed")
  user_id, session_id = "seed-admin", str(uuid.uuid4())
  await runner.session_service.create_session(
      app_name="zoho_hr_seed", user_id=user_id, session_id=session_id
  )

  prompt = (
      "Set up the demo departments, employees, and leave types in both "
      "Zoho People and Zoho Payroll, as instructed."
  )

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
