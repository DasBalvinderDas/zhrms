"""One-time admin script: seeds demo employees into the connected Zoho
Creator HR app, so the demo use cases in scripts/run_demo.py have real data
to query.

    python scripts/seed_demo_data.py

Uses a separate, wider set of Zoho MCP tools than the conversational agent
(zoho_hr_agent.agent.root_agent) -- addRecords, which writes data, which the
day-to-day HR assistant intentionally does not have access to.

Driven by an LLM rather than hardcoded field names, because the connected
app's exact forms/reports/fields are account-specific and only discoverable
at runtime via getApplications/getForms/getReports/get*Metadata. If a form
has a field that can't reasonably be filled via API (e.g. a mandatory photo
upload), the agent is instructed to report that plainly rather than
fabricate a value -- if you hit that, make the field optional in the
Creator app builder (Edit this application -> the form -> the field ->
uncheck Mandatory) and re-run.

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
    "ZohoCreator_getApplications",
    "ZohoCreator_getForms",
    "ZohoCreator_getReports",
    "ZohoCreator_getFormMetadata",
    "ZohoCreator_getReportMetadata",
    "ZohoCreator_getCreatorRecords",
    "ZohoCreator_addRecords",
]

SEED_INSTRUCTION = """\
You are a one-time setup assistant seeding demo employees into a Zoho
Creator HR application.

1. Call getApplications to find the HR application (look for one named
   something like "Human Resource Management" -- don't assume the exact
   name, use whatever getApplications actually returns).
2. Call getForms and getReports for that app to find the employee form (an
   "Add Employee"-style form) and a report that lists existing employee
   records (to check for duplicates before creating).
3. Call getFormMetadata on the employee form to see its actual fields
   before creating anything. If any mandatory field can't reasonably be
   filled via API (e.g. a required photo/file upload with no file
   available), do NOT invent a fake value -- report exactly which field is
   blocking creation and stop, don't create partial/invalid records.
4. Otherwise, using getCreatorRecords on the employee report to check for
   existing matches by email first, ensure these three employees exist
   (addRecords if missing), filling only the fields the form actually has,
   with today's date for any required "date of joining"-style field and
   sensible values for anything else mandatory (including a CTC/
   compensation value if that field is mandatory -- pick something
   reasonable and say what you chose):
   - Asha Verma, asha.verma@demo-coe-org.example, Engineering, Software Engineer
   - Rahul Nair, rahul.nair@demo-coe-org.example, Engineering, Engineering Manager
   - Priya Shah, priya.shah@demo-coe-org.example, Human Resources, HR Executive
5. If a leave-request form/report exists, note its name in your summary but
   don't create sample leave requests -- leave that for interactive use.

Work through all of this one item at a time. After each creation attempt,
state plainly whether it succeeded, already existed, or failed (with the
error). Finish with a short summary table of created vs. already-existed
vs. failed.
"""


async def main() -> None:
  agent = Agent(
      name="zoho_seed_agent",
      model=os.environ.get("ADK_MODEL", "gemini-2.5-flash"),
      description="One-time admin agent that seeds demo Zoho Creator HR data.",
      instruction=SEED_INSTRUCTION,
      tools=[build_zoho_toolset(tool_filter=SEED_TOOL_FILTER)],
  )

  runner = InMemoryRunner(agent=agent, app_name="zoho_hr_seed")
  user_id, session_id = "seed-admin", str(uuid.uuid4())
  await runner.session_service.create_session(
      app_name="zoho_hr_seed", user_id=user_id, session_id=session_id
  )

  prompt = "Set up the demo employees in the Zoho Creator HR app, as instructed."

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
