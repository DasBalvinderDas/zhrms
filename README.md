# Zoho HR/Payroll Agent (ADK + Zoho MCP) — POC

Small proof-of-concept showing a [Google ADK](https://google.github.io/adk-docs/)
agent talking to Zoho People (HR) and Zoho Payroll data through **Zoho's own
MCP server** — no custom Zoho API glue code, no bespoke tool wrappers. ADK's
`MCPToolset` connects straight to Zoho's hosted MCP endpoint and turns
whatever tools Zoho exposes into agent-callable tools at runtime.

```
 ADK LlmAgent (Gemini)
        │  MCPToolset (Streamable HTTP)
        ▼
 Zoho MCP server  (https://mcp.zoho.com/...)
        │
        ├── Zoho People   (employee directory, leave)
        └── Zoho Payroll  (payslips, payroll runs)
```

## Use cases demoed

1. **Employee lookup** — "Look up Jane Doe" → employee directory tools.
2. **Leave** — check leave balance and submit a leave request → Zoho
   People leave-module tools.
3. **Payroll** — fetch the latest payslip / a payroll run summary → Zoho
   Payroll tools.

The agent's instructions (`zoho_hr_agent/agent.py`) constrain it to these
three areas and tell it to only report data actually returned by the MCP
tools — never to fabricate employee or pay data.

## 1. Set up the Zoho MCP server

1. Sign in to the [Zoho MCP console](https://www.zoho.com/mcp/) and create a
   server (`Create MCP Server`, or start from a pre-configured one).
2. `Add Tools` → select the **People** and **Payroll** products, and enable
   the employee/leave and payslip/payroll-run tools you want to demo.
3. Complete the OAuth authorization for those products.
4. Open the server's **Connect** tab and copy the generated MCP URL — it's
   unique per server and already carries an API key, e.g.
   `https://mcp.zoho.com/api/mcp/<server-id>?api_key=<key>`.

Full walkthrough: [Zoho MCP Implementation Guide](https://help.zoho.com/portal/en/kb/mcp/implementation-guide/articles/zoho-mcp-implementation-guide).

## 2. Configure this project (GCP Cloud Shell)

This POC uses Vertex AI for Gemini, authenticated with your GCP project via
Application Default Credentials — no API key needed.

```bash
# one-time per Cloud Shell environment
gcloud config set project YOUR_PROJECT_ID
gcloud services enable aiplatform.googleapis.com
gcloud auth application-default login

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env:
#   GOOGLE_CLOUD_PROJECT  -> your GCP project ID
#   GOOGLE_CLOUD_LOCATION -> e.g. us-central1 (must have Vertex AI Gemini access)
#   ZOHO_MCP_URL          -> the MCP URL you copied above
```

Your Cloud Shell user needs the `roles/aiplatform.user` IAM role on the
project (or broader) to call Gemini via Vertex AI.

If you'd rather skip Vertex AI and use a plain AI Studio key instead, set
`GOOGLE_GENAI_USE_VERTEXAI=FALSE` and `GOOGLE_API_KEY=...` in `.env` — the
rest of the project is unaffected either way.

## 3. Try it

Confirm connectivity and see exactly which tools your server exposes
(the tool catalog depends entirely on what you enabled in step 1):

```bash
python scripts/discover_tools.py
```

Run the three scripted use cases end-to-end:

```bash
python scripts/run_demo.py
```

Or drive it interactively with ADK's own UI/CLI:

```bash
adk web      # browser chat UI, pick "zoho_hr_agent"
adk run zoho_hr_agent
```

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
- Auth here relies on the per-server API key embedded in `ZOHO_MCP_URL`
  (Zoho's default). `ZOHO_MCP_API_KEY` is available if you switch the server
  to header-based auth instead.
- Not covered yet, natural next steps for a wider POC: multi-turn employee
  disambiguation, write-actions confirmation (e.g. "are you sure?" before
  submitting leave), and swapping `InMemorySessionService` for a persistent
  one.
