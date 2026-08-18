# Zoho HR Agent (ADK + Zoho MCP) — POC

Small proof-of-concept showing a [Google ADK](https://google.github.io/adk-docs/)
agent talking to HR data in a Zoho Creator app through **Zoho's own MCP
server** — no custom Zoho API glue code, no bespoke tool wrappers. ADK's
`MCPToolset` connects straight to Zoho's hosted MCP endpoint and turns
whatever tools Zoho exposes into agent-callable tools at runtime.

```
 ADK LlmAgent (Gemini via Vertex AI)
        │  MCPToolset (Streamable HTTP)
        ▼
 Zoho MCP server  (https://<your-server>.zohomcp.in/mcp/...)
        │
        └── Zoho Creator  (HR app: employees, leave, compensation)
```

> This started out targeting **Zoho People** (and briefly **Zoho Payroll**)
> for HR/payroll data, but the connected Zoho account turned out to have no
> real organization set up in either product — only a custom-built Zoho
> Creator app ("Human Resource Management"). Everything now runs off that
> one app instead. If your account genuinely has Zoho People/Payroll set
> up, their tools work the same shape as Creator's here, just with
> different, HR-specific tool names — see the note in `zoho_hr_agent/agent.py`.

**Use cases demoed:**

1. **Employee lookup** — find an employee by name and summarize their
   profile → Zoho Creator's generic record tools against the app's employee
   report.
2. **Workforce insights** — headcount/org breakdown by department →
   aggregated by the agent from the same employee records (no dedicated
   insights tool exists for a custom Creator app).
3. **Leave** — look up leave records/history, and submit a new leave
   request if the app has a leave form → Zoho Creator record tools.
4. **Compensation** — report an employee's CTC from their employee record.
   (There's no separate pay-run/payslip system here — just whatever
   compensation field the Creator app's employee form has.)
5. **Burnout-risk triage (HR ops)** — flag employees worth a human check-in
   based on leave frequency/recency (the only workload proxy this app has,
   no ticketing/time-tracking data is used). Explicitly framed as a data
   pattern for HR to follow up on, never as a clinical/medical claim.
6. **Attrition / resignation lookup** — who's resigned, their last working
   day, and stated reason → Zoho Creator record tools against the app's
   resignation report.
7. **Company announcements** — list/summarize recent company-wide
   announcements → Zoho Creator record tools against the app's
   announcement report.

The agent's instructions (`zoho_hr_agent/agent.py`) constrain it to these
five areas and tell it to only report data actually returned by the MCP
tools — never to fabricate employee, leave, or compensation data. Because a
Creator app's forms/reports/fields are specific to whichever app is
connected, the agent is instructed to *discover* them at runtime
(`getApplications` → `getForms`/`getReports` → `get*Metadata`) rather than
assume fixed names.

---

## Setup (GCP Cloud Shell)

### Step 1 — Get the project into Cloud Shell

Open [Cloud Shell](https://shell.cloud.google.com/) and clone this repo /
branch, or upload it if you already have it locally:

```bash
git clone https://github.com/DasBalvinderDas/zhrms.git
cd zhrms
git checkout claude/zoho-mcp-hr-agent-qt153i
```

### Step 2 — Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3 — Create your `.env` file

All configuration for this project — GCP project, region, Zoho MCP URL —
lives in one `.env` file. Create it now; the next two steps tell you exactly
which line to fill in as you go.

```bash
cp .env.example .env
```

Open it in the Cloud Shell editor (or `nano .env`) and keep it open — you'll
add values to it in Steps 4 and 5.

`.env` is git-ignored — it's never committed, so it's safe to put real
credentials there. Never paste its contents into a commit, issue, or chat
message.

### Step 4 — Enable Vertex AI on your GCP project

The agent calls Gemini through Vertex AI using your GCP project, authenticated
with Application Default Credentials — no separate API key needed.

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable aiplatform.googleapis.com
gcloud auth application-default login
```

Your Cloud Shell user (or the identity running this) needs the
`roles/aiplatform.user` IAM role on the project to call Gemini.

Now fill these two lines into `.env`:

| Variable | Value |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | your GCP project ID (same as `YOUR_PROJECT_ID` above) |
| `GOOGLE_CLOUD_LOCATION` | a region with Vertex AI Gemini access, e.g. `us-central1` |

### Step 5 — Get a Zoho MCP server URL

If you don't already have one:

1. Sign in to the Zoho MCP console for your data center (e.g.
   `mcp.zoho.in` or `mcp.zoho.com`) and create a server.
2. **Tools** → `Add Tools` → select **Zoho Creator** → the specific app
   holding your HR data (e.g. a "Human Resource Management" app) — enable
   its generic tool group (forms/reports/records — `getApplications`,
   `getForms`, `getReports`, `get*Metadata`, `getCreatorRecords`,
   `addRecords`, etc.). That's it; nothing else is required for this POC.
3. **Connection** → switch the authorization mode to **"Authorize via
   Connection"** (it starts on "Authorize on Demand"). This matters: "on
   demand" means every MCP client has to complete its own interactive OAuth
   browser login against the server, which doesn't work from a headless
   shell or a deployed agent. "Via Connection" has *you* (the admin)
   pre-authorize every tool once, in the console, and bakes that
   authorization into the server URL itself — no login needed at connection
   time. Confirm the switch; it regenerates the URL's embedded token.
4. Open the **Connect** tab and copy the generated MCP URL, e.g.:
   `https://<your-server>.zohomcp.in/mcp/<token>/message`

Full walkthrough: [Zoho MCP Implementation Guide](https://help.zoho.com/portal/en/kb/mcp/implementation-guide/articles/zoho-mcp-implementation-guide).

If you were already handed a URL like the one above (and it's already on
"Authorize via Connection"), you can skip straight to filling it in.

Now fill this line into `.env`:

| Variable | Value |
|---|---|
| `ZOHO_MCP_URL` | the MCP URL from above |

Leave `ZOHO_MCP_API_KEY` blank and `ZOHO_MCP_TRANSPORT=streamable_http` as-is
— the token embedded in `ZOHO_MCP_URL` is all that's needed once the server
is on "Authorize via Connection." (If Step 6 fails with a transport/session
error, try `ZOHO_MCP_TRANSPORT=sse` instead — see Troubleshooting.)

### Step 6 — Verify the Zoho MCP connection

```bash
python scripts/discover_tools.py
```

This connects to your Zoho MCP server and prints every tool it exposes —
confirms the URL/auth are correct, and shows you the real tool names before
the agent ever runs (they depend on which tool group you enabled in Step 5).

### Step 7 — Seed demo data

Seed 7 fully-detailed demo employees (every profile field the form has,
not just the mandatory ones, plus compensation linkage), a full September
2026 leave calendar with a deliberately varied pattern across the team —
some employees with frequent/recent leave, some light, some none at all,
one too new to read "no leave" as a signal — one resignation record, and
three company announcements, so there's real data for all seven use cases
above to reason over, via Zoho's own MCP tools:

```bash
python scripts/seed_demo_data.py
```

This resets and reseeds: it deletes any existing records matching the
specific demo values first, then recreates them fresh, rather than
checking-and-skipping — so it always leaves the same known-good state
whether the app currently has none, some, or all of this data already. It
only ever touches those specific demo records, nothing else in the app. It
uses a separate, wider set of Zoho MCP tools (`addRecords`/`deleteRecords`,
which write/delete data) than the conversational agent.

One known limitation: if a form has a field that can't reasonably be
filled via API (e.g. a mandatory photo/file upload, or a mandatory
picklist with no real choices configured), it'll say so rather than
fabricate a value. Fix that in the Creator app builder (**Edit this
application** → the form → the field → uncheck **Mandatory**, or add real
choices) and re-run. As of this writing, the resignation record is
skipped this way — `Apply_Resignation`'s `Resignation_Letter` field is a
mandatory file upload with no file to send via this API.

### Step 8 — Run the demo

Scripted run of the four use cases in one session:

```bash
python scripts/run_demo.py
```

Or drive it interactively with ADK's own UI/CLI:

```bash
adk web      # browser chat UI (use Cloud Shell's Web Preview), pick "zoho_hr_agent"
adk run zoho_hr_agent
```

---

## Troubleshooting

- **`discover_tools.py` fails with `401` on the MCP request** — the server is
  still on "Authorize on Demand" (Step 5.3). Switch it to "Authorize via
  Connection" in the console's **Connection** tab, copy the *new* URL (the
  switch regenerates the embedded token, invalidating the old one), and
  update `ZOHO_MCP_URL` in `.env`.
  - Don't try to work around this with `mcp-remote`'s interactive OAuth flow
    from Cloud Shell — the browser's redirect back to `localhost:<port>`
    lands on your laptop, not the Cloud Shell VM, so it can't complete
    without extra port-forwarding gymnastics. "Authorize via Connection"
    avoids needing that login at all, which is also the right shape for a
    headless deployment (e.g. Agent Engine) later.
- **A form's `addRecords` call fails because of a mandatory field that
  can't be filled via API** (e.g. a photo upload) — fix it in the Creator
  app builder rather than working around it: **Edit this application** →
  the form → the field → uncheck **Mandatory** (or remove the field if you
  don't need it).
- **`discover_tools.py` hangs or errors about the transport/session** — the
  URL may need the legacy SSE transport instead of Streamable HTTP. Set
  `ZOHO_MCP_TRANSPORT=sse` in `.env` and re-run.
- **403 / permission denied calling Gemini** — your account is missing
  `roles/aiplatform.user`, or `aiplatform.googleapis.com` isn't enabled on
  the project (Step 4), or `GOOGLE_CLOUD_LOCATION` doesn't have Gemini
  available.
- **404 "Publisher model ... was not found" calling Gemini** — the model in
  `ADK_MODEL` isn't available as a Vertex AI publisher model in your
  project/region (older model IDs get superseded over time). Set
  `ADK_MODEL=gemini-2.5-flash` in `.env`, or check the Model Garden in the
  Cloud Console for a currently available model ID in your region.
- **`discover_tools.py` connects but returns 0 tools** — no tool group is
  enabled on the Zoho MCP server yet (Step 5.2), or `ZOHO_MCP_TOOL_FILTER` in
  `.env` is filtering everything out (leave it blank to see everything).
- **Want AI Studio instead of Vertex AI?** — set
  `GOOGLE_GENAI_USE_VERTEXAI=FALSE` and `GOOGLE_API_KEY=...` in `.env`
  instead of the three `GOOGLE_CLOUD_*` variables. Everything else stays the
  same.

---

## Files

```
zoho_hr_agent/
  agent.py            # MCPToolset -> Zoho MCP, LlmAgent with HR instructions
scripts/
  discover_tools.py   # connects and lists available Zoho MCP tools
  seed_demo_data.py   # resets and reseeds demo employees/leave in the Creator app
  run_demo.py         # scripted run of the 4 use cases via InMemoryRunner
.env.example           # required/optional environment variables
```

## Notes / next steps

- This POC exposes whatever tools the Zoho MCP server is configured with; no
  tool names are hard-coded into the connection logic, so it degrades
  gracefully to "not available" if a module isn't enabled. Narrow the surface
  with `ZOHO_MCP_TOOL_FILTER` in `.env` once you know the exact tool names
  from `discover_tools.py`.
- Zoho Creator's tools are generic (forms/reports/records), not HR-specific
  -- there's no built-in "employee insights" or "leave balance" concept like
  Zoho People has, and no pay-run/payslip system like Zoho Payroll has. The
  agent aggregates/interprets from raw records instead, which is less
  precise than a purpose-built HR API but works for a demo.
- **Known limitation**: non-Lookup fields inside a Zoho Creator subform
  (e.g. the Monthly/Annual pay amounts in this app's "Salary Structure" ->
  "Salary Split Up" subform) can't be written through this MCP server's
  `addRecords`/`updateRecordByID` tools -- confirmed via `scripts/call_tool.py`
  against a live record: the call reports success, but only the subform's
  Lookup field persists; currency/text/decision fields are silently
  dropped, across multiple payload formats. Enter those values through the
  Creator app's own UI instead; reads work fine once the data's there. See
  `scripts/seed_demo_data.py`'s docstring for the full investigation.
- **Known limitation**: the resignation record isn't seeded by default --
  `Apply_Resignation`'s `Resignation_Letter` field is a mandatory file
  upload with no file to send via this JSON-based API, which blocks the
  whole record. Uncheck **Mandatory** on that field in the Creator app
  builder (same fix as the employee `Photo` field earlier) and re-run
  `seed_demo_data.py` to pick it up.
- Not covered yet, natural next steps for a wider POC: write-actions
  confirmation (e.g. "are you sure?" before submitting leave), and swapping
  `InMemorySessionService` for a persistent one ahead of an Agent Engine
  deployment.
