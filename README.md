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
        ├── Zoho People   (employee directory, leave)
        └── Zoho Payroll  (payslips, payroll runs)
```

**Use cases demoed:**

1. **Employee lookup** — "Look up Jane Doe" → employee directory tools.
2. **Leave** — check leave balance and submit a leave request → Zoho
   People leave-module tools.
3. **Payroll** — fetch the latest payslip / a payroll run summary → Zoho
   Payroll tools.

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

### Step 3 — Enable Vertex AI on your GCP project

The agent calls Gemini through Vertex AI using your GCP project, authenticated
with Application Default Credentials — no separate API key needed.

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable aiplatform.googleapis.com
gcloud auth application-default login
```

Your Cloud Shell user (or the identity running this) needs the
`roles/aiplatform.user` IAM role on the project to call Gemini.

### Step 4 — Get a Zoho MCP server URL

If you don't already have one:

1. Sign in to the Zoho MCP console for your data center (e.g.
   `mcp.zoho.in` or `mcp.zoho.com`) and create a server.
2. `Add Tools` → select the **People** and **Payroll** products, and enable
   the employee/leave and payslip/payroll-run tools you want to demo.
3. Complete the OAuth authorization for those products.
4. Open the server's **Connect** tab and copy the generated MCP URL. It
   already carries your server's auth token embedded in the URL, e.g.:
   `https://<server-name>.zohomcp.in/mcp/<token>/message`

Full walkthrough: [Zoho MCP Implementation Guide](https://help.zoho.com/portal/en/kb/mcp/implementation-guide/articles/zoho-mcp-implementation-guide).

If you were already handed a URL like the one above, skip straight to Step 5.

### Step 5 — Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Value |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | your GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | a region with Vertex AI Gemini access, e.g. `us-central1` |
| `ZOHO_MCP_URL` | the MCP URL from Step 4 |

Leave `ZOHO_MCP_API_KEY` blank and `ZOHO_MCP_TRANSPORT=streamable_http` as-is
— the auth token embedded in `ZOHO_MCP_URL` is all that's needed. (If Step 6
fails with a transport/session error, try `ZOHO_MCP_TRANSPORT=sse` instead —
see Troubleshooting.)

`.env` is git-ignored — it's never committed, so it's safe to put real
credentials there. Never paste the filled-in URL into a commit, issue, or
chat message.

### Step 6 — Verify the Zoho MCP connection

```bash
python scripts/discover_tools.py
```

This connects to your Zoho MCP server and prints every tool it exposes —
confirms the URL/auth are correct, and shows you the real tool names before
the agent ever runs (they depend on which tool groups you enabled in Step 4).

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

- **`discover_tools.py` hangs or errors about the transport/session** — the
  URL may need the legacy SSE transport instead of Streamable HTTP. Set
  `ZOHO_MCP_TRANSPORT=sse` in `.env` and re-run.
- **403 / permission denied calling Gemini** — your account is missing
  `roles/aiplatform.user`, or `aiplatform.googleapis.com` isn't enabled on
  the project (Step 3), or `GOOGLE_CLOUD_LOCATION` doesn't have Gemini
  available.
- **`discover_tools.py` connects but returns 0 tools** — no tool groups are
  enabled on the Zoho MCP server yet, or `ZOHO_MCP_TOOL_FILTER` in `.env` is
  filtering everything out (leave it blank to see everything).
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
