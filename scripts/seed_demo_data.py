"""One-time admin script: wipes and recreates seven fully-detailed demo
employees (all profile fields, not just the mandatory ones), links each to
a compensation record, seeds a full September 2026 leave calendar with a
deliberately varied pattern per employee, one resignation record, and a
handful of company announcements, in the connected Zoho Creator HR app.
This gives the demo use cases in scripts/run_demo.py -- including
burnout-risk triage, which reads leave frequency/recency as its workload
proxy, and attrition/announcement lookups -- real, consistent data to
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
anything, in case the app has changed since. The Resignation and
Announcement forms were confirmed to exist in the app (visible in its nav:
"Resignation", "Announcement" -> "Add Announcement"/"All Announcements"),
but their exact field names were NOT inspected ahead of time -- the script
describes what each record should mean in plain terms and lets the agent
map that onto whatever getFormMetadata actually returns, same as every
other form here. The one field it does NOT fill is Photo (a file/image
upload -- there's no file to send via this JSON-based API); it reports
that plainly rather than fabricate one.

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
Creator HR application: seven fully-detailed employees, their compensation
linkage, a full September 2026 leave calendar with a deliberately varied
pattern across the whole team, one resignation record, and three company
announcements. The app may currently have none, some, or all of this data
from a previous run -- don't assume any particular starting state. Delete
whatever demo records already exist first, then create everything fresh,
so the end state is always the same regardless of the starting point. Only
ever touch records matching the specific demo values below -- never
delete or modify anything else in the app.

Do not assume field names or picklist choices from this prompt alone --
call getFormMetadata on each form before writing to it, and match every
attribute below to whatever field/choice actually exists. If a field
mentioned below no longer exists, skip just that field and continue; if a
picklist's real choices don't include an exact match for a value below,
pick the closest real choice and say what you picked instead. This
applies especially to the Resignation and Announcement forms below -- their
exact field names were not inspected ahead of time, only that the forms
exist; map the described content onto whatever real fields
getFormMetadata shows (e.g. a title/subject field, a body/description
field, a date field) rather than assuming specific field names.

=== Discover ===

1. Call getApplications to find the HR application (look for one named
   something like "Human Resource Management" -- use whatever
   getApplications actually returns, don't assume the exact name).
2. Call getForms and getReports for that app to find: the employee form/
   report, department/designation/location forms/reports, the
   compensation/salary-structure form/report and its pay-component form,
   the leave-request and leave-type forms/reports (likely under a "Leave
   Tracker" menu), the resignation form/report, and the announcement
   form/report (likely "Add Announcement" for writing, "All Announcements"
   for reading).
3. Call getFormMetadata on the employee, resignation, and announcement
   forms to see their actual fields and choices. The only field you should
   NOT attempt to fill is a photo/file upload -- there's no file to send
   via this API. Every other field, mandatory or not, should be filled
   with a real, sensible value; don't stop at just the mandatory subset.

=== Delete existing demo data (in this order, to respect references) ===

4. In the announcement report, delete any existing demo announcements
   matching these titles/subjects via deleteRecords: "Diwali Holiday -
   Office Closure", "New Work-From-Home Policy Rollout", "Welcome Our New
   Team Members - September 2026".
5. In the resignation report, delete any existing resignation record
   referencing arjun.kapoor@demo-coe-org.example via deleteRecords.
6. In the leave report, delete ALL existing leave request(s) for these
   seven people via deleteRecords (match by employee, however that's
   represented in that report -- email, name, or a lookup to the employee
   record): asha.verma@demo-coe-org.example, rahul.nair@demo-coe-org.example,
   priya.shah@demo-coe-org.example, vikram.mehta@demo-coe-org.example,
   sneha.iyer@demo-coe-org.example, arjun.kapoor@demo-coe-org.example,
   neha.joshi@demo-coe-org.example.
7. In the employee report, delete any existing records matching these
   seven emails via deleteRecords.
8. In the compensation/salary-structure report, delete any existing
   records for these seven people (they'll be labeled something like
   "<Name> CTC" -- match by that pattern) via deleteRecords.
9. In the department/designation/location reports, delete any existing
   records matching these specific demo values via deleteRecords:
   departments "Engineering", "Human Resources", "Product", "Sales";
   designations "Software Engineer", "Engineering Manager", "HR
   Executive", "Product Manager", "Sales Executive", "Data Analyst",
   "DevOps Engineer"; locations "Bangalore" and "Remote".

=== Recreate fresh ===

10. Recreate the department/designation/location master records from step
    9 via addRecords. Ensure a pay component named "Base Salary" exists in
    its form/report too (create if missing).
11. Recreate a compensation/salary-structure record per employee (e.g.
    "Asha Verma CTC" ... "Neha Joshi CTC"), each referencing the "Base
    Salary" pay component. Note each new record's own ID -- you need it in
    step 12.
    IMPORTANT: the subform's Monthly field is mandatory at creation time,
    so you MUST include a Monthly value (and Annual, if present) in the
    create call or the whole record will be rejected -- use these
    plausible monthly values (Annual = Monthly * 12): Asha 100000, Rahul
    150000, Priya 75000, Vikram 130000, Sneha 90000, Arjun 85000, Neha
    95000. This is a known-broken write path (see this file's module
    docstring): the amount will likely NOT actually persist even though
    the create call succeeds and returns an ID. That's fine -- what
    matters here is that the record and its ID exist so it CAN be linked
    to the employee in step 12. Don't spend extra attempts trying to make
    the amount persist; one create call with a value included is enough.
    Note in your summary that amounts need to be entered manually in the
    Creator app UI afterward.
12. Create the employees in this order: Rahul Nair, Priya Shah, Asha
    Verma, Vikram Mehta, Sneha Iyer, Arjun Kapoor, Neha Joshi. For EVERY
    field the employee form actually has (per its real metadata), fill it
    using these consistent profiles. Where a field isn't listed below, use
    a sensible, realistic value consistent with the rest of that person's
    profile -- don't leave fillable fields blank.

    Reporting_To: check this field's real type in the form metadata
    before touching it. If it's a Lookup to the employee report, set
    Asha, Vikram, Sneha, Arjun, and Neha to report to Rahul Nair (his new
    employee record ID, same bare-ID pattern as the other Lookup fields).
    If it's actually a plain picklist (as discovered in one run, where its
    only real choice was "-") rather than a true employee-reference field,
    leave it unset for everyone -- don't force an invalid picklist value
    just to represent a reporting relationship the field isn't actually
    configured to hold. Say which case you found.

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
    - CTC: her Salary Structure record's own ID from step 11

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
    - CTC: his Salary Structure record's own ID from step 11

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
    - CTC: her Salary Structure record's own ID from step 11

    Vikram Mehta: Product Manager, Product, Bangalore.
    - Personal_Email: vikram.personal@example.com; Official_Email:
      vikram.mehta@demo-coe-org.example
    - Mobile_Number: +91 9845012345; Gender: Male
    - Employee_ID: EM004; Date_of_Joining: 03-Sep-2020
    - Date_of_Birth: 14-Jan-1990; Marital_Status: Married; Blood_Group: A+
    - Seat_Location: "4th Floor, Bay 3"
    - Father_s_Name: Rajesh Mehta; Mother_s_Name: Sunita Mehta
    - Emergency_Contact_Person: Pooja Mehta; Relationship: Spouse;
      Contact_Number: +91 9812345670
    - Present_Address1 and Permanent_Address1 (same): address_line_1
      "88, Whitefield Main Road", district_city "Bangalore",
      state_province "Karnataka", postal_code "560066", country "India"
    - Hobbies: "Chess, Trekking"
    - CTC: his Salary Structure record's own ID from step 11

    Sneha Iyer: Sales Executive, Sales, Remote.
    - Personal_Email: sneha.personal@example.com; Official_Email:
      sneha.iyer@demo-coe-org.example
    - Mobile_Number: +91 9787654321; Gender: Female
    - Employee_ID: EM005; Date_of_Joining: 20-Jan-2023
    - Date_of_Birth: 05-Sep-1996; Marital_Status: Single; Blood_Group: B-
    - Seat_Location: "Remote - Home Office"
    - Father_s_Name: Mohan Iyer; Mother_s_Name: Lakshmi Iyer
    - Emergency_Contact_Person: Lakshmi Iyer; Relationship: Mother;
      Contact_Number: +91 9765123408
    - Present_Address1 and Permanent_Address1 (same): address_line_1
      "12, Besant Nagar", district_city "Chennai", state_province
      "Tamil Nadu", postal_code "600090", country "India"
    - Hobbies: "Badminton, Photography"
    - CTC: her Salary Structure record's own ID from step 11

    Arjun Kapoor: Data Analyst, Engineering, Bangalore.
    - Personal_Email: arjun.personal@example.com; Official_Email:
      arjun.kapoor@demo-coe-org.example
    - Mobile_Number: +91 9856701234; Gender: Male
    - Employee_ID: EM006; Date_of_Joining: 12-Aug-2021
    - Date_of_Birth: 30-Nov-1994; Marital_Status: Single; Blood_Group: O-
    - Seat_Location: "3rd Floor, Bay 5"
    - Father_s_Name: Deepak Kapoor; Mother_s_Name: Ritu Kapoor
    - Emergency_Contact_Person: Deepak Kapoor; Relationship: Father;
      Contact_Number: +91 9823456701
    - Present_Address1 and Permanent_Address1 (same): address_line_1
      "27, HSR Layout", district_city "Bangalore", state_province
      "Karnataka", postal_code "560102", country "India"
    - Hobbies: "Gaming, Cycling"
    - CTC: his Salary Structure record's own ID from step 11
    - This employee resigns in step 15 -- still fill his profile
      completely here; the resignation is a separate record, not a
      reason to leave employee fields blank.

    Neha Joshi: DevOps Engineer, Engineering, Remote.
    - Personal_Email: neha.personal@example.com; Official_Email:
      neha.joshi@demo-coe-org.example
    - Mobile_Number: +91 9898123456; Gender: Female
    - Employee_ID: EM007; Date_of_Joining: 17-Aug-2026 -- keep this exact,
      recent date; it matters for how step 14's leave data should be
      interpreted (she's too new to read "no leave yet" as a signal).
    - Date_of_Birth: 22-Apr-1997; Marital_Status: Single; Blood_Group: AB+
    - Seat_Location: "Remote - Home Office"
    - Father_s_Name: Prakash Joshi; Mother_s_Name: Meena Joshi
    - Emergency_Contact_Person: Meena Joshi; Relationship: Mother;
      Contact_Number: +91 9834567012
    - Present_Address1 and Permanent_Address1 (same): address_line_1
      "5, Baner Road", district_city "Pune", state_province
      "Maharashtra", postal_code "411045", country "India"
    - Hobbies: "Running, Reading"
    - CTC: her Salary Structure record's own ID from step 11

    Lookup fields (Location, Department, Designation, CTC, and
    Reporting_To if it turns out to genuinely be a Lookup per the check
    above) reference records in other forms/reports. If a plain display-name
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

13. Ensure leave types "Casual Leave" and "Sick Leave" exist (create via
    the leave-type form if missing).
14. Create this leave history -- a full September 2026 calendar plus the
    existing earlier-year leaves for the original three, deliberately
    different per employee so there's a real, visible pattern across the
    whole team, not just one flat sample:
    - Asha Verma (frequent/recent -- a burnout-risk signal, continuing
      into September): Casual Leave 08-Jun-2026 to 09-Jun-2026 ("Family
      function"); Sick Leave 20-Jul-2026 to 22-Jul-2026 ("Feeling
      unwell"); Casual Leave 10-Aug-2026 to 10-Aug-2026 ("Personal
      work"); Casual Leave 03-Sep-2026 to 04-Sep-2026 ("Family
      function"); Sick Leave 22-Sep-2026 to 22-Sep-2026 ("Feeling
      unwell").
    - Rahul Nair (light, nothing recent): Casual Leave 12-Feb-2026 to
      13-Feb-2026 ("Family event"). No September leave -- deliberately,
      to contrast with Asha and Vikram.
    - Priya Shah (none on record at all -- a different kind of signal):
      create no leave requests for her.
    - Vikram Mehta (the most frequent leave-taker in September -- the
      strongest burnout-risk signal in this dataset): Casual Leave
      01-Sep-2026 to 02-Sep-2026 ("Personal work"); Sick Leave
      08-Sep-2026 to 09-Sep-2026 ("Feeling unwell"); Casual Leave
      15-Sep-2026 to 15-Sep-2026 ("Family function"); Casual Leave
      24-Sep-2026 to 25-Sep-2026 ("Personal work").
    - Sneha Iyer (moderate, unremarkable): Casual Leave 12-Sep-2026 to
      13-Sep-2026 ("Family function").
    - Arjun Kapoor (moderate, unremarkable): Casual Leave 05-Sep-2026 to
      05-Sep-2026 ("Personal work").
    - Neha Joshi (none yet -- but she only joined 17-Aug-2026, so this is
      NOT a "hasn't taken a break in a long stretch" signal, just a brand
      new joiner; state that distinction explicitly in your summary so it
      isn't misread): create no leave requests for her.

15. Resignation: in the resignation form/report, create one record for
    Arjun Kapoor (EM006, arjun.kapoor@demo-coe-org.example). Map the
    following onto whatever fields getFormMetadata actually shows (an
    employee reference/lookup, a resignation date, a last working day, a
    reason, and a notice-period/status field are the likely shapes, but
    check rather than assume): Employee -> Arjun Kapoor (his new employee
    record ID via the bare-ID Lookup pattern, if that field is a Lookup;
    otherwise his name/email if it's a plain reference); Resignation
    date -> 01-Sep-2026; Last working day -> 30-Sep-2026; Reason ->
    "Pursuing higher studies"; Notice period / status -> whichever real
    choice most plausibly means "serving notice" / "in progress" (pick
    the closest real choice and say what you picked).

16. Company announcements: in the announcement form/report (write via
    whatever form backs "Add Announcement"), create these three records.
    Map onto whatever fields actually exist (a title/subject field, a
    body/content/description field, a date field, and an
    audience/category field if present):
    - Title -> "Diwali Holiday - Office Closure"; Content -> "The office
      will remain closed on 10-Nov-2026 for Diwali. Wishing everyone a
      happy and safe festival."; Date -> 01-Sep-2026.
    - Title -> "New Work-From-Home Policy Rollout"; Content -> "Starting
      October 2026, employees may work from home up to two days a week
      with manager approval. See the HR portal for the full policy
      document."; Date -> 15-Sep-2026.
    - Title -> "Welcome Our New Team Members - September 2026"; Content ->
      "Please join us in welcoming Vikram Mehta (Product), Sneha Iyer
      (Sales), Arjun Kapoor (Engineering), and Neha Joshi (Engineering) to
      the team this quarter!"; Date -> 18-Sep-2026.

Work through all of this one item at a time. After each delete/create
attempt, state plainly whether it succeeded, found nothing to delete, or
failed (with the error) -- and for the employee records specifically, list
which fields you successfully set vs. skipped and why. Finish with a
summary table covering all seven employees' status and CTC linkage
status, every leave request's status, the resignation record's status,
and each announcement's status.
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
