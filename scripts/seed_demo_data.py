"""One-time admin script: wipes and recreates three fully-detailed demo
employees (all profile fields, not just the mandatory ones), links each to
a compensation record, and seeds a deliberately varied leave history per
employee, in the connected Zoho Creator HR app. This gives the demo use
cases in scripts/run_demo.py -- including burnout-risk triage, which reads
leave frequency/recency as its workload proxy -- real, consistent data to
reason over, regardless of whatever partial state (none, some, all) is
already there.

    python scripts/seed_demo_data.py

Deletes any existing records matching the specific demo values below
before recreating them, rather than checking-and-skipping. This is a
demo/POC seeding script, not a production migration -- deterministic
reset-and-reseed is simpler and more reliable here than incremental
patching. It does NOT touch anything in the app that isn't one of these
specific demo records.

Uses a separate, wider set of Zoho MCP tools than the conversational agent
(zoho_hr_agent.agent.root_agent) -- addRecords/deleteRecords, which write
and delete data, which the day-to-day HR assistant intentionally does not
have access to.

Driven by an LLM rather than hardcoded field names, because the connected
app's exact forms/reports/fields are account-specific and only discoverable
at runtime via getApplications/getForms/getReports/get*Metadata. Field
names below (Name, Present_Address1, Marital_Status, etc.) come from a live
getCreatorRecords(field_config: "all") dump during development, not
guesswork -- but the script still calls getFormMetadata itself at runtime
to read the real, current field list and picklist choices before writing
anything, in case the app has changed since. The one field it does NOT
fill is Photo (a file/image upload -- there's no file to send via this
JSON-based API); it reports that plainly rather than fabricate one.

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
agent already knows to read from that subform. The employee's own CTC
lookup field (linking to their Salary Structure record) IS set by this
script -- that part uses the same bare-record-ID Lookup pattern already
proven for Department/Designation/Location, and is a separate, working
piece from the subform amounts.
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
Creator HR application: three fully-detailed employees, their compensation
linkage, and a deliberately varied leave history per employee. The app may
currently have none, some, or all of this data from a previous run --
don't assume any particular starting state. Delete whatever demo records
already exist first, then create everything fresh, so the end state is
always the same regardless of the starting point. Only ever touch records
matching the specific demo values below -- never delete or modify anything
else in the app.

Do not assume field names or picklist choices from this prompt alone --
call getFormMetadata on each form before writing to it, and match every
attribute below to whatever field/choice actually exists. If a field
mentioned below no longer exists, skip just that field and continue; if a
picklist's real choices don't include an exact match for a value below,
pick the closest real choice and say what you picked instead.

=== Discover ===

1. Call getApplications to find the HR application (look for one named
   something like "Human Resource Management" -- use whatever
   getApplications actually returns, don't assume the exact name).
2. Call getForms and getReports for that app to find: the employee form/
   report, department/designation/location forms/reports, the
   compensation/salary-structure form/report and its pay-component form,
   and the leave-request and leave-type forms/reports.
3. Call getFormMetadata on the employee form to see its actual fields and
   their choices. The only field you should NOT attempt to fill is a
   photo/file upload -- there's no file to send via this API. Every other
   field, mandatory or not, should be filled with a real, sensible value;
   don't stop at just the mandatory subset.

=== Delete existing demo data (in this order, to respect references) ===

4. In the leave report, delete ALL existing leave request(s) for these
   three people via deleteRecords (match by employee, however that's
   represented in that report -- email, name, or a lookup to the employee
   record): asha.verma@demo-coe-org.example, rahul.nair@demo-coe-org.example,
   priya.shah@demo-coe-org.example.
5. In the employee report, delete any existing records matching these
   three emails via deleteRecords.
6. In the compensation/salary-structure report, delete any existing
   records for these three people (they'll be labeled something like
   "<Name> CTC" -- match by that pattern) via deleteRecords.
7. In the department/designation/location reports, delete any existing
   records matching these specific demo values via deleteRecords:
   departments "Engineering" and "Human Resources"; designations
   "Software Engineer", "Engineering Manager", "HR Executive"; locations
   "Bangalore" and "Remote".

=== Recreate fresh ===

8. Recreate the department/designation/location master records from step 7
   via addRecords. Ensure a pay component named "Base Salary" exists in
   its form/report too (create if missing).
9. Recreate a compensation/salary-structure record per employee (e.g.
   "Asha Verma CTC", "Rahul Nair CTC", "Priya Shah CTC"), each referencing
   the "Base Salary" pay component. Note each new record's own ID -- you
   need it in step 10. Don't spend more than one attempt trying to set the
   subform's actual Monthly/Annual pay amounts -- that write path is
   known-broken (see this file's module docstring for the confirmed root
   cause); note in your summary that amounts need to be entered manually
   in the Creator app UI instead of retrying formats.
10. Create Rahul Nair and Priya Shah first (they have no manager in this
    demo), then Asha Verma referencing Rahul's new employee record ID as
    her manager -- see the Reporting_To note below. For EVERY field the
    employee form actually has (per its real metadata), fill it using
    these three consistent profiles. Where a field isn't listed below, use
    a sensible, realistic value consistent with the rest of that person's
    profile -- don't leave fillable fields blank.

    Asha Verma: Software Engineer, Engineering, Bangalore.
    - Personal_Email: asha.personal@example.com; Official_Email:
      asha.verma@demo-coe-org.example
    - Mobile_Number: +91 9876543210; Gender: Female
    - Employee_ID: EM001; Date_of_Joining: 15-Mar-2022
    - Date_of_Birth: 27-Oct-1995; Marital_Status: Single; Blood_Group: O+
    - Seat_Location: "3rd Floor, Bay 12"
    - Father_s_Name: Suresh Verma; Mother_s_Name: Anita Verma
    - Emergency_Contact_Person: Anita Verma; Relationship: Mother;
      Contact_Number: +91 9765432109
    - Present_Address1 and Permanent_Address1 (same): address_line_1
      "221B, Indiranagar", district_city "Bangalore", state_province
      "Karnataka", postal_code "560038", country "India"
    - Hobbies: "Reading, Hiking"
    - Reporting_To: Rahul Nair's employee record ID (a Lookup field --
      pass his bare record ID as a scalar string, same pattern as
      Department/Designation/Location; see the Lookup-field note below)
    - CTC: her Salary Structure record's own ID from step 9 (same
      bare-ID Lookup pattern)

    Rahul Nair: Engineering Manager, Engineering, Remote.
    - Personal_Email: rahul.personal@example.com; Official_Email:
      rahul.nair@demo-coe-org.example
    - Mobile_Number: +91 9123456780; Gender: Male
    - Employee_ID: EM002; Date_of_Joining: 01-Jun-2019
    - Date_of_Birth: 10-May-1988; Marital_Status: Married;
      Blood_Group: B+
    - Seat_Location: "Remote - Home Office"
    - Father_s_Name: Ramesh Nair; Mother_s_Name: Sunita Nair
    - Emergency_Contact_Person: Meera Nair; Relationship: Spouse;
      Contact_Number: +91 9988776655
    - Present_Address1 and Permanent_Address1 (same): address_line_1
      "14, Anna Nagar 2nd Street", district_city "Chennai",
      state_province "Tamil Nadu", postal_code "600040", country "India"
    - Hobbies: "Cricket, Cooking"
    - Reporting_To: leave unset (top of this small demo org)
    - CTC: his Salary Structure record's own ID from step 9

    Priya Shah: HR Executive, Human Resources, Bangalore.
    - Personal_Email: priya.personal@example.com; Official_Email:
      priya.shah@demo-coe-org.example
    - Mobile_Number: +91 9012345678; Gender: Female
    - Employee_ID: EM003; Date_of_Joining: 11-Jan-2021
    - Date_of_Birth: 18-Feb-1993; Marital_Status: Single;
      Blood_Group: A-
    - Seat_Location: "2nd Floor, HR Wing"
    - Father_s_Name: Anil Shah; Mother_s_Name: Kavita Shah
    - Emergency_Contact_Person: Anil Shah; Relationship: Father;
      Contact_Number: +91 9871234560
    - Present_Address1 and Permanent_Address1 (same): address_line_1
      "45, Koramangala 5th Block", district_city "Bangalore",
      state_province "Karnataka", postal_code "560095", country "India"
    - Hobbies: "Painting, Yoga"
    - Reporting_To: leave unset (no HR manager in this small demo org)
    - CTC: her Salary Structure record's own ID from step 9

    Lookup fields (Location, Department, Designation, CTC, Reporting_To)
    reference records in other forms/reports. If a plain display-name
    string or an {"ID": ...}-style object gets rejected with an "Invalid
    column value" error, pass the referenced record's ID as a bare string
    value with no object wrapper at all (e.g. "Location": "<record id>")
    -- Zoho's error message for a rejected object echoes the whole object
    back as "the value", meaning it wants a scalar there, not an object.
    If that still fails, try the lookup form's display/unique field name
    as a bare string instead of its ID. Only if every reasonable format
    is exhausted should you report that specific field as blocking
    creation -- don't let one field's failure stop you from filling the
    rest of the record.

11. Ensure leave types "Casual Leave" and "Sick Leave" exist (create via
    the leave-type form if missing).
12. Create this leave history -- deliberately different per employee, so
    there's a real pattern to reason over later, not just one flat sample:
    - Asha Verma (frequent/recent -- a burnout-risk signal): three leave
      requests -- Casual Leave 08-Jun-2026 to 09-Jun-2026 ("Family
      function"); Sick Leave 20-Jul-2026 to 22-Jul-2026 ("Feeling
      unwell"); Casual Leave 10-Aug-2026 to 10-Aug-2026 ("Personal work").
    - Rahul Nair (light -- one leave, nothing recent): one leave request
      -- Casual Leave 12-Feb-2026 to 13-Feb-2026 ("Family event").
    - Priya Shah (none on record -- a different kind of signal): create
      no leave requests for her at all.

Work through all of this one item at a time. After each delete/create
attempt, state plainly whether it succeeded, found nothing to delete, or
failed (with the error) -- and for the employee records specifically, list
which fields you successfully set vs. skipped and why. Finish with a
summary table covering all three employees' status, their CTC linkage
status, and each leave request's status.
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
