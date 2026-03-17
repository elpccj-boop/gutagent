"""FastAPI server for GutAgent web UI."""

import json
import os
import secrets
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()  # Load .env file

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from gutagent.config import TOOLS, MAX_TOKENS, LLM_PROVIDER, get_model_for_tier
from gutagent.profile import load_profile
from gutagent.db.models import init_db
from gutagent.prompts.system import build_static_system_prompt, build_dynamic_context
from gutagent.tools.registry import execute_tool


# Initialize
init_db()

app = FastAPI(title="GutAgent")

# Security
security = HTTPBasic()

# Load credentials from environment
AUTH_USERNAME = os.getenv("GUTAGENT_USERNAME", "")
AUTH_PASSWORD = os.getenv("GUTAGENT_PASSWORD", "")

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify username and password."""
    # If no credentials configured, skip auth (local development)
    if not AUTH_USERNAME or not AUTH_PASSWORD:
        return True

    username_correct = secrets.compare_digest(credentials.username, AUTH_USERNAME)
    password_correct = secrets.compare_digest(credentials.password, AUTH_PASSWORD)

    if not (username_correct and password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session storage for recent_logs and last_exchange (for corrections)
# Keyed by session_id, stores {"recent_logs": {...}, "last_exchange": {...}}
sessions: dict[str, dict] = {}


# Tools that create log entries — we track their results for edit context
LOG_TOOLS = {
    "log_meal": "meals",
    "log_symptom": "symptoms",
    "log_vital": "vitals",
    "log_medication_event": "medications",
    "log_sleep": "sleep",
    "log_exercise": "exercise",
    "log_journal": "journal",
}


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"  # For tracking recent_logs/last_exchange
    model: str = "default"  # "default" (fast/cheap) or "smart" (capable)
    show_tools: bool = False


def get_model(tier: str) -> str:
    """Get model string for the current provider and tier."""
    return get_model_for_tier(tier)


def format_recent_logs(recent_logs: dict) -> str:
    """Format recent_logs dict into a string for the prompt."""
    if not recent_logs:
        return ""

    lines = ["Recently logged (available for edits):"]
    for table, entries in recent_logs.items():
        for entry in entries:
            entry_id = entry.get("id", "?")
            desc = (
                entry.get("summary") or
                entry.get("description") or
                entry.get("symptom") or
                entry.get("vital_type") or
                entry.get("type") or
                entry.get("reading") or
                entry.get("medication") or
                entry.get("event_type") or
                str(entry)[:50]
            )
            lines.append(f"  [{table}] id:{entry_id} — {desc}")

    return "\n".join(lines)


async def run_agent_streaming(
    user_message: str,
    profile: dict,
    model: str,
    session_id: str,
    show_tools: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Streaming version of the agent loop.
    Yields Server-Sent Events as Claude generates responses.

    Tracks recent_logs and last_exchange per session for corrections.
    """
    import anthropic
    client = anthropic.Anthropic()

    # Get or create session state
    if session_id not in sessions:
        sessions[session_id] = {"recent_logs": {}, "last_exchange": {}}

    session = sessions[session_id]
    recent_logs = session["recent_logs"]
    last_exchange = session["last_exchange"]

    # Build system prompt
    static_prompt = build_static_system_prompt(profile)
    dynamic_context = build_dynamic_context()

    # Add recent logs context if we have any
    logs_context = format_recent_logs(recent_logs)
    if logs_context:
        dynamic_context = dynamic_context + "\n\n" + logs_context

    system_prompt = static_prompt + "\n\n" + dynamic_context

    # Messages for this turn - include last exchange for minimal context
    messages = []
    if last_exchange.get("user") and last_exchange.get("assistant"):
        messages.append({"role": "user", "content": last_exchange["user"]})
        messages.append({"role": "assistant", "content": last_exchange["assistant"]})
    messages.append({"role": "user", "content": user_message})

    # Track logs created this turn
    logs_this_turn = {}
    
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Stream from Claude
        current_text = ""
        tool_uses = []

        with client.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "text":
                        current_text = ""
                    elif event.content_block.type == "tool_use":
                        tool_uses.append({
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input": "",
                        })
                        if show_tools:
                            yield f"data: {json.dumps({'type': 'tool_start', 'name': event.content_block.name})}\n\n"

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        current_text += event.delta.text
                        # Stream text chunks to client
                        yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"
                    elif event.delta.type == "input_json_delta":
                        # Accumulate tool input JSON
                        if tool_uses:
                            tool_uses[-1]["input"] += event.delta.partial_json

                elif event.type == "content_block_stop":
                    if current_text:
                        current_text = ""
        
            # Get final message for stop reason
            final_message = stream.get_final_message()
        
        if final_message.stop_reason == "tool_use":
            # Build content list with tool uses
            assistant_content = []
            for block in final_message.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            messages.append({
                "role": "assistant",
                "content": assistant_content,
            })
            
            # Execute tools
            tool_results = []
            for block in final_message.content:
                if block.type == "tool_use":
                    tool_name = block.name

                    if show_tools:
                        yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'input': block.input})}\n\n"

                    result = execute_tool(tool_name, block.input)

                    if show_tools:
                        # Truncate for display
                        display_result = result[:300] + "..." if len(result) > 300 else result
                        yield f"data: {json.dumps({'type': 'tool_result', 'name': tool_name, 'result': display_result})}\n\n"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                    # Track log operations
                    if tool_name in LOG_TOOLS:
                        table = LOG_TOOLS[tool_name]
                        try:
                            entry = json.loads(result)
                            if "id" in entry:
                                if table not in logs_this_turn:
                                    logs_this_turn[table] = []
                                logs_this_turn[table].append(entry)
                        except (json.JSONDecodeError, TypeError):
                            pass

            # Add tool results to messages for next iteration
            messages.append({
                "role": "user",
                "content": tool_results,
            })
            
            # Continue loop
        else:
            # Final text response
            response_text = ""
            for block in final_message.content:
                if hasattr(block, "text"):
                    response_text += block.text

            # Update session state
            for table, entries in logs_this_turn.items():
                recent_logs[table] = entries
            
            session["recent_logs"] = recent_logs
            session["last_exchange"] = {
                "user": user_message,
                "assistant": response_text[:500]
            }

            # Signal end of stream
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
    
    # Safety: max iterations reached
    yield f"data: {json.dumps({'type': 'error', 'message': 'Max iterations reached'})}\n\n"


@app.post("/api/chat")
async def chat(request: ChatRequest, authenticated: bool = Depends(verify_credentials)):
    """Stream a chat response. Tracks recent_logs and last_exchange for corrections."""
    profile = load_profile()
    model = get_model(request.model)
    
    return StreamingResponse(
        run_agent_streaming(
            user_message=request.message,
            profile=profile,
            model=model,
            session_id=request.session_id,
            show_tools=request.show_tools,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/context")
async def get_context(authenticated: bool = Depends(verify_credentials)):
    """Get current dynamic context (recent data)."""
    from gutagent.prompts.system import get_dynamic_context, get_nutrition_alerts_text
    
    return {
        "context": get_dynamic_context(),
        "alerts": get_nutrition_alerts_text(),
    }


@app.get("/api/profile")
async def get_profile(authenticated: bool = Depends(verify_credentials)):
    """Get the user profile."""
    return load_profile()


# Serve static files (web UI)
web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")


def main():
    """Run the server."""
    import uvicorn

    auth_status = "🔒 Auth enabled" if AUTH_USERNAME and AUTH_PASSWORD else "⚠️  No auth (set GUTAGENT_USERNAME and GUTAGENT_PASSWORD)"

    print("\n🥗 GutAgent Web UI")
    print(f"   {auth_status}")
    print("   Local:   http://localhost:8000")
    print("   Network: http://<your-ip>:8000")
    print("\n   Press Ctrl+C to stop\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
