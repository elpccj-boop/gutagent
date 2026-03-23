"""FastAPI server for GutAgent web UI."""

import json
import os
import secrets
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from gutagent.config import TOOLS, MAX_TOKENS, get_model_for_tier
from gutagent.profile import load_profile
from gutagent.db import init_db, set_rda_targets
from gutagent.tools.registry import execute_tool
from gutagent.core import (
    LOG_TOOLS,
    MAX_ITERATIONS,
    format_recent_logs,
    build_messages,
    track_log_operation,
    finalize_turn,
)
from gutagent.prompts.system import build_static_system_prompt, build_dynamic_context
from gutagent.paths import WEB_DIR


# Initialize
init_db()
profile = load_profile()
set_rda_targets(profile)

app = FastAPI(title="GutAgent")

# Security
security = HTTPBasic()

# Load credentials from environment
AUTH_USERNAME = os.getenv("GUTAGENT_USERNAME", "")
AUTH_PASSWORD = os.getenv("GUTAGENT_PASSWORD", "")


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify username and password."""
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

# Session storage for recent_logs and last_exchange
sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    model: str = "default"
    show_tools: bool = False


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

    Note: Currently Claude-only. Provider abstraction for streaming not yet implemented.
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

    logs_context = format_recent_logs(recent_logs)
    if logs_context:
        dynamic_context = dynamic_context + "\n\n" + logs_context

    # Use list format for Claude prompt caching
    system_prompt = [
        {"type": "text", "text": static_prompt, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic_context}
    ]

    # Build messages using shared logic
    messages = build_messages(user_message, last_exchange)

    # Track logs created this turn
    logs_this_turn = {}

    iteration = 0
    
    while iteration < MAX_ITERATIONS:
        iteration += 1
        
        # Stream from Claude
        current_text = ""

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
                        if show_tools:
                            yield f"data: {json.dumps({'type': 'tool_start', 'name': event.content_block.name})}\n\n"

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        current_text += event.delta.text
                        yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"

                elif event.type == "content_block_stop":
                    if current_text:
                        current_text = ""

            final_message = stream.get_final_message()

        # Send token usage
        if hasattr(final_message, 'usage') and final_message.usage:
            usage = final_message.usage
            usage_data = {
                'type': 'usage',
                'input_tokens': usage.input_tokens,
                'output_tokens': usage.output_tokens,
                'cache_creation_input_tokens': getattr(usage, 'cache_creation_input_tokens', 0),
                'cache_read_input_tokens': getattr(usage, 'cache_read_input_tokens', 0),
            }
            yield f"data: {json.dumps(usage_data)}\n\n"
        
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
                    tool_input = block.input

                    if show_tools:
                        yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'input': tool_input})}\n\n"

                    result = execute_tool(tool_name, tool_input)

                    if show_tools:
                        display_result = result[:300] + "..." if len(result) > 300 else result
                        yield f"data: {json.dumps({'type': 'tool_result', 'name': tool_name, 'result': display_result})}\n\n"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                    # Track log operations using shared logic
                    track_log_operation(tool_name, tool_input, result, recent_logs, logs_this_turn)

            messages.append({
                "role": "user",
                "content": tool_results,
            })

        else:
            # Final text response
            response_text = ""
            for block in final_message.content:
                if hasattr(block, "text"):
                    response_text += block.text

            # Finalize turn using shared logic
            new_last_exchange = finalize_turn(
                user_message=user_message,
                response_text=response_text,
                recent_logs=recent_logs,
                logs_this_turn=logs_this_turn,
            )
            
            session["recent_logs"] = recent_logs
            session["last_exchange"] = new_last_exchange

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

    yield f"data: {json.dumps({'type': 'error', 'message': 'Max iterations reached'})}\n\n"


@app.post("/api/chat")
async def chat(request: ChatRequest, authenticated: bool = Depends(verify_credentials)):
    """Stream a chat response."""
    profile = load_profile()
    model = get_model_for_tier(request.model)
    
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
async def get_profile_endpoint(authenticated: bool = Depends(verify_credentials)):
    """Get the user profile."""
    return load_profile()


# Serve static files (web UI)
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


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
