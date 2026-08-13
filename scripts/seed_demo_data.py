"""One-time admin script: wipes and recreates demo employees (with
compensation) and one sample leave request in the connected Zoho Creator HR
app, so the demo use cases in scripts/run_demo.py always have the same
complete, known-good data to query -- regardless of whatever partial state
(none, some, all) is already there.

    python scripts/seed_demo_data.py

Deletes any existing records matching the specific demo values below (by
email for employees, by name for the department/designation/location
master records, by employee for the leave request) before recreating them,
rather than checking-and-skipping. This is a demo/POC seeding script, not
a production migration -- deterministic reset-and-reseed is simpler and
more reliable here than incremental patching. It does NOT touch anything
in the app that isn't one of these specific demo records.

Uses a separate, wider set of Zoho MCP tools than the conversational agent
(zoho_hr_agent.agent.root_agent) -- addRecords/deleteRecords, which write
and delete data, which the day-to-day HR assistant intentionally does not
have access to.

Driven by an LLM rather than hardcoded field names, because the connected
app's exact forms/reports/fields are account-specific and only discoverable
at runtime via getApplications/getForms/getReports/get*Metadata. If a form
has a field that can't reasonably be filled via API (e.g. a mandatory photo
upload, or a mandatory picklist with no real choices configured), the agent
is instructed to report that plainly rather than fabricate a value -- if
you hit that, fix it in the Creator app builder (Edit this application ->
the form -> the field -> uncheck Mandatory, or add real choices) and
re-run.

KNOWN LIMITATION -- this script does NOT set Monthly/Annual pay amounts on
the "Salary Structure" record's "Salary Split Up" subform, even though it
tries. Verified via scripts/call_tool.py against a live record: addRecords/
updateRecordByID all report success, but every non-Lookup field in that
subform (Monthly, Annual, Formula, Is_Deduction -- currency/text/decision
types) is silently dropped on every write; only the Lookup field
(Pay_Component) ever persists. Confirmed across three payload variants
(numbers, decimal strings, all fields explicit) with identical results --
this is a limitation of the MCP tool's subform write path, not a payload
format issue. Enter Monthly/Annual for each employee's Salary Structure
record manually through the Creator app's own UI instead; that write path
doesn't hit the same bug. Once entered, no code changes are needed -- the
agent already knows to read from that subform.
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
    "ZohoCreator_getApplications",
    "ZohoCreator_getForms",
    "ZohoCreator_getReports",
    "ZohoCreator_getFormMetadata",
    "ZohoCreator_getReportMetadata",
    "ZohoCreator_getCreatorRecords",
    "ZohoCreator_addRecords",
    "ZohoCreator_deleteRecords",
]

SEED_INSTRUCTION = """\
You are a setup assistant that resets and reseeds demo data in a Zoho
Creator HR application: three employees (with compensation) and one sample
leave request. The app may currently have none, some, or all of this data
from a previous run -- don't assume any particular starting state. Delete
whatever demo records already exist first, then create everything fresh,
so the end state is always the same regardless of the starting point. Only
ever touch records matching the specific demo values below -- never delete
or modify anything else in the app.

=== Discover ===

1. Call getApplications to find the HR application (look for one named
   something like "Human Resource Management" -- don't assume the exact
   name, use whatever getApplications actually returns).
2. Call getForms and getReports for that app to find: the employee form/
   report, the department/designation/location forms/reports, and any
   leave-request form/report.
3. Call getFormMetadata on the employee form to see its actual fields. If
   any mandatory field can't reasonably be filled via API (e.g. a required
   photo/file upload, or a mandatory picklist whose only configured choice
   is an empty placeholder), do NOT invent a fake value -- report exactly
   which field is blocking creation and stop, don't create partial/invalid
   records.

=== Delete existing demo data (in this order, to respect references) ===

4. In the leave report, delete any existing leave request(s) for Asha
   Verma (asha.verma@demo-coe-org.example) via deleteRecords with a
   criteria matching her.
5. In the employee report, delete any existing records matching these
   three emails via deleteRecords:
   asha.verma@demo-coe-org.example, rahul.nair@demo-coe-org.example,
   priya.shah@demo-coe-org.example.
6. In the department/designation/location reports, delete any existing
   records matching these specific demo values via deleteRecords:
   departments "Engineering" and "Human Resources"; designations
   "Software Engineer", "Engineering Manager", "HR Executive"; locations
   used for these employees (e.g. any you find named "Bangalore" or
   "Remote").

=== Recreate fresh ===

7. Recreate the department/designation/location master records from step 6
   via addRecords.
8. Recreate these three employees via addRecords, using every field the
   form has, with today's date for any required "date of joining"-style
   field, and sensible values for anything else mandatory:
   - Asha Verma, asha.verma@demo-coe-org.example, Engineering, Software Engineer
   - Rahul Nair, rahul.nair@demo-coe-org.example, Engineering, Engineering Manager
   - Priya Shah, priya.shah@demo-coe-org.example, Human Resources, HR Executive

   If the employee form (or a linked salary/compensation report it points
   to) has a CTC/compensation field, ensure a record for it exists and is
   linked to the employee (e.g. a "Salary Structure" record referencing a
   pay component), but don't spend more than one attempt trying to set the
   actual Monthly/Annual pay amounts within a subform -- writing those
   amounts via this MCP tool is a known-broken path (see this file's
   module docstring for the confirmed root cause); note in your summary
   that amounts need to be entered manually in the Creator app UI instead
   of retrying formats.

   Lookup fields (Location, Department, Designation, and possibly
   compensation) reference records in other forms. If a plain display-name
   string or an {"ID": ...}-style object gets rejected with an "Invalid
   column value" error, try passing the referenced record's ID as a bare
   string value with no object wrapper at all (e.g. "Location": "<record
   id>") -- Zoho's error message for a rejected object echoes the whole
   object back as "the value", which means it wants a scalar there, not an
   object. If that still fails, try the lookup form's display/unique field
   name as a bare string instead of its ID. Only if every reasonable
   format is exhausted should you report the field as blocking creation.
9. If a leave-request form/report exists, call getFormMetadata on it and
   submit exactly one sample leave request for Asha Verma (a short,
   plausible date range a few weeks out, with whatever reason/leave-type
   field the form has set to something reasonable) via addRecords. Don't
   create leave requests for the other two employees -- one sample record
   is enough to demonstrate the use case.

Work through all of this one item at a time. After each delete/create
attempt, state plainly whether it succeeded, found nothing to delete, or
failed (with the error). Finish with a short summary table covering all
three employees' status and the leave request status.
"""


async def main() -> None:
  agent = Agent(
      name="zoho_seed_agent",
      model=os.environ.get("ADK_MODEL", "gemini-2.5-flash"),
      description="Admin agent that resets and reseeds demo Zoho Creator HR data.",
      instruction=SEED_INSTRUCTION,
      tools=[build_zoho_toolset(tool_filter=SEED_TOOL_FILTER)],
  )

  runner = InMemoryRunner(agent=agent, app_name="zoho_hr_seed")
  user_id, session_id = "seed-admin", str(uuid.uuid4())
  await runner.session_service.create_session(
      app_name="zoho_hr_seed", user_id=user_id, session_id=session_id
  )

  prompt = "Reset and reseed the demo data in the Zoho Creator HR app, as instructed."

  saw_any_output = False
  try:
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
      if not event.content or not event.content.parts:
        continue
      for part in event.content.parts:
        if getattr(part, "function_call", None):
          fc = part.function_call
          print(f"[tool call] {fc.name}({str(fc.args)[:200]})")
          saw_any_output = True
        elif getattr(part, "function_response", None):
          fr = part.function_response
          print(f"[tool result] {fr.name} -> {str(fr.response)[:300]}")
          saw_any_output = True
        elif getattr(part, "text", None):
          print(part.text.strip())
          saw_any_output = True
    if not saw_any_output:
      print("(agent produced no output at all -- check ZOHO_MCP_TOOL_FILTER, "
            "the model name, and Vertex AI access)")
  finally:
    await runner.close()


if __name__ == "__main__":
  asyncio.run(main())
