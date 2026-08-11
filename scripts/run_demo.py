"""Scripted walkthrough of the three POC use cases against the live agent.

    python scripts/run_demo.py
    python scripts/run_demo.py "What leave types do we have configured?"

With no arguments it runs one prompt for each use case (workforce insights,
leave, payroll) in a single session. Pass your own prompt(s) as CLI args to
try something else instead.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.genai import types
from google.adk.runners import InMemoryRunner

from zoho_hr_agent.agent import root_agent

DEFAULT_PROMPTS = [
    # 1. Workforce insights
    "Give me a headcount breakdown by department for my team.",
    # 2. Leave
    "What leave types are configured, and what's my current leave balance?",
    # 3. Payroll
    "Show me the most recent pay run and the pay details for its employees "
    "-- gross pay, deductions, and net pay.",
]


async def main() -> None:
  prompts = sys.argv[1:] or DEFAULT_PROMPTS

  runner = InMemoryRunner(agent=root_agent, app_name="zoho_hr_poc")
  user_id, session_id = "demo-user", str(uuid.uuid4())
  await runner.session_service.create_session(
      app_name="zoho_hr_poc", user_id=user_id, session_id=session_id
  )

  try:
    for prompt in prompts:
      print(f"\n>>> {prompt}")
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
