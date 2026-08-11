# Zoho HR/Payroll Agent (ADK + Zoho MCP) — POC

Small proof-of-concept showing a [Google ADK](https://google.github.io/adk-docs/)
agent talking to Zoho People (HR) and Zoho Payroll data through **Zoho's own
MCP server** — no custom Zoho API glue code, no bespoke tool wrappers. ADK's
`MCPToolset` connects straight to Zoho's hosted MCP endpoint and turns
whatever tools Zoho exposes into agent-callable tools at runtime.

```
 ADK LlmAgent (Gemini via Vertex AI)
        │  MCPToolset (Streamable HTTP)
        ▼
 Zoho MCP server  (https://<your-server>.zohomcp.in/mcp/...)
        │
        ├── Zoho People   (workforce insights, leave)
        └── Zoho Payroll  (pay runs, employee pay details)
```

**Use cases demoed:**

1. **Workforce insights** — headcount/org breakdown by department,
   designation, location → Zoho People's `employeeInsights` tool.
2. **Leave** — check leave types/balance and submit a leave request → Zoho
   People leave-module tools.
3. **Payroll** — pull up a pay run and an employee's pay details within it
   (gross pay, deductions, net pay) → Zoho Payroll pay-run tools.

The agent's instructions (`zoho_hr_agent/agent.py`) constrain it to these
three areas and tell it to only report data actually returned by the MCP
tools — never to fabricate employee or pay data.

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
2. **Tools** → `Add Tools` → select **Zoho People** and **Zoho Payroll**, and
   enable the Leave, Reports/Insights, and Pay Run tool groups (whatever
   modules you want the agent to reach).
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
the agent ever runs (they depend on which tool groups you enabled in Step 5).

### Step 7 — Run the demo

Scripted run of the three use cases in one session:

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
- **`discover_tools.py` hangs or errors about the transport/session** — the
  URL may need the legacy SSE transport instead of Streamable HTTP. Set
  `ZOHO_MCP_TRANSPORT=sse` in `.env` and re-run.
- **403 / permission denied calling Gemini** — your account is missing
  `roles/aiplatform.user`, or `aiplatform.googleapis.com` isn't enabled on
  the project (Step 4), or `GOOGLE_CLOUD_LOCATION` doesn't have Gemini
  available.
- **`discover_tools.py` connects but returns 0 tools** — no tool groups are
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
  agent.py           # MCPToolset -> Zoho MCP, LlmAgent with HR/payroll instructions
scripts/
  discover_tools.py  # connects and lists available Zoho MCP tools
  run_demo.py         # scripted run of the 3 use cases via InMemoryRunner
.env.example          # required/optional environment variables
```

## Notes / next steps

- This POC exposes whatever tools the Zoho MCP server is configured with; no
  tool names are hard-coded, so it degrades gracefully to "not available" if
  a module isn't enabled. Narrow the surface with `ZOHO_MCP_TOOL_FILTER` in
  `.env` once you know the exact tool names from `discover_tools.py`.
- Not covered yet, natural next steps for a wider POC: multi-turn employee
  disambiguation, write-actions confirmation (e.g. "are you sure?" before
  submitting leave), and swapping `InMemorySessionService` for a persistent
  one.
