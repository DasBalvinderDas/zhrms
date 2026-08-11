"""One-time admin script: seeds demo employees and leave data into the
connected Zoho Creator HR app, plus matching departments/designations/work
location/employees into Zoho Payroll, so the demo use cases in
scripts/run_demo.py have real data to query.

    python scripts/seed_demo_data.py

Uses a separate, wider set of Zoho MCP tools than the conversational agent
(zoho_hr_agent.agent.root_agent) -- tools that create/modify data, which the
day-to-day HR/payroll assistant intentionally does not have access to.

The Zoho Creator side is driven by an LLM rather than hardcoded field names,
because the connected app's exact forms/reports/fields are account-specific
and only discoverable at runtime via getApplications/getForms/getReports/
get*Metadata. If a form has a field that can't reasonably be filled via API
(e.g. a mandatory photo upload), the agent is instructed to report that
plainly rather than fabricate a value.

Not covered: Payroll salary assignment and pay run creation. Nothing in the
currently available Payroll tool set can set an employee's base salary
(only fetch/list tools exist for salary templates/components) -- that still
has to happen once in the Payroll web UI (payroll.zoho.in) before a pay run
will have real numbers in it.

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
    # Zoho Creator: generic app/form/report/record discovery + write tools.
    "ZohoCreator_getApplications",
    "ZohoCreator_getForms",
    "ZohoCreator_getReports",
    "ZohoCreator_getFormMetadata",
    "ZohoCreator_getReportMetadata",
    "ZohoCreator_getCreatorRecords",
    "ZohoCreator_addRecords",
    # Zoho Payroll: organization resolution + dedicated org-structure/employee tools.
    "ZohoPayroll_list_organizations",
    "ZohoPayroll_get_organization",
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
You are a one-time setup assistant seeding demo data across a Zoho Creator
HR app and Zoho Payroll. They're separate systems with separate employee
records -- set up both.

Before creating anything, check what already exists and skip anything
that's already there -- do not create duplicates.

=== Zoho Creator ===

1. Call getApplications to find the HR application (look for one named
   something like "Human Resource Management" -- don't assume the exact
   name, use whatever getApplications actually returns).
2. Call getForms and getReports for that app to find the employee form (an
   "Add Employee"-style form) and, if one exists, a leave-request form.
   Also find a report that lists existing employee records (to check for
   duplicates before creating).
3. Call getFormMetadata on the employee form to see its actual fields
   before creating anything. If any mandatory field can't reasonably be
   filled via API (e.g. a required photo/file upload with no file
   available), do NOT invent a fake value -- report that this blocks
   creating employees via this form, and stop the Creator portion here.
4. Otherwise, using getCreatorRecords on the employee report to check for
   existing matches by email first, ensure these three employees exist
   (addRecords if missing), filling only the fields the form actually has,
   with today's date for any required "date of joining"-style field and
   sensible values for anything else mandatory:
   - Asha Verma, asha.verma@demo-coe-org.example, Engineering, Software Engineer
   - Rahul Nair, rahul.nair@demo-coe-org.example, Engineering, Engineering Manager
   - Priya Shah, priya.shah@demo-coe-org.example, Human Resources, HR Executive
5. If a leave-request form/report exists, note its name in your summary but
   don't create sample leave requests -- leave that for interactive use.

=== Zoho Payroll ===

6. Call list_organizations first and use its result as the organization ID
   for every subsequent Payroll call -- never guess an organization ID.
7. Ensure these departments exist (create_department if missing):
   - Engineering
   - Human Resources
8. Ensure these designations exist (create_designation if missing):
   - Software Engineer
   - Engineering Manager
   - HR Executive
9. Ensure one work location exists (create_work_location if missing) --
   use the organization's own registered address if the tool needs one,
   otherwise a reasonable default name like "Head Office".
10. Ensure the same three employees exist in Payroll (create_employee if
    missing), referencing the department/designation/work location records
    from steps 7-9. Read create_employee's own parameter schema for exactly
    which fields it requires, and use sensible values (e.g. today as date
    of joining) for anything mandatory not specified above.

Do NOT attempt to assign salaries or create a pay run -- no available tool
can set an employee's salary, so leave that for manual setup.

Work through all of this one item at a time. After each creation attempt,
state plainly whether it succeeded, already existed, or failed (with the
error). Finish with a short summary table of created vs. already-existed
vs. failed, split by Zoho Creator vs. Zoho Payroll.
"""


async def main() -> None:
  agent = Agent(
      name="zoho_seed_agent",
      model=os.environ.get("ADK_MODEL", "gemini-2.5-flash"),
      description="One-time admin agent that seeds demo Zoho Creator/Payroll data.",
      instruction=SEED_INSTRUCTION,
      tools=[build_zoho_toolset(tool_filter=SEED_TOOL_FILTER)],
  )

  runner = InMemoryRunner(agent=agent, app_name="zoho_hr_seed")
  user_id, session_id = "seed-admin", str(uuid.uuid4())
  await runner.session_service.create_session(
      app_name="zoho_hr_seed", user_id=user_id, session_id=session_id
  )

  prompt = (
      "Set up the demo employees in the Zoho Creator HR app, and the "
      "matching departments/designations/work location/employees in Zoho "
      "Payroll, as instructed."
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
