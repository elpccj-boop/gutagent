"""FastAPI server for GutAgent web UI."""

import json
import os
import secrets
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()  # Load .env file

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from gutagent.config import TOOLS, MAX_TOKENS, LLM_PROVIDER, get_model_for_tier
from gutagent.profile import load_profile
from gutagent.db import init_db, set_rda_targets
from gutagent.tools.registry import execute_tool
from gutagent.paths import WEB_DIR
from gutagent.core import (
    MAX_ITERATIONS,
    build_system_prompt,
    build_messages,
    track_log_operation,
    finalize_turn,
)


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


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"  # For tracking recent_logs/last_exchange
    model: str = "default"  # "default" (fast/cheap) or "smart" (capable)
    show_tools: bool = False


def get_model(tier: str) -> str:
    """Get model string for the current provider and tier."""
    return get_model_for_tier(tier)


async def run_agent_streaming(
    user_message: str,
    profile: dict,
    model: str,
    session_id: str,
    show_tools: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Streaming version of the agent loop.
    Yields Server-Sent Events as the LLM generates responses.

    Supports Claude (with caching) and Gemini providers.
    Tracks recent_logs and last_exchange per session for corrections.
    """
    from gutagent.llm import get_provider

    # Get or create session state
    if session_id not in sessions:
        sessions[session_id] = {"recent_logs": {}, "last_exchange": {}}

    session = sessions[session_id]
    recent_logs = session["recent_logs"]
    last_exchange = session["last_exchange"]

    # Build system prompt using core function
    static_prompt, dynamic_context = build_system_prompt(profile, recent_logs)

    # Build messages using core function
    messages = build_messages(user_message, last_exchange)

    # Track logs created this turn
    logs_this_turn = {}

    # Get LLM provider
    try:
        llm = get_provider(LLM_PROVIDER, model=model)
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to initialize {LLM_PROVIDER}: {str(e)}'})}\n\n"
        return

    try:
        for iteration in range(MAX_ITERATIONS):
            if LLM_PROVIDER == "claude":
                # Claude-specific streaming with full event handling and caching
                # Format system prompt for Claude caching
                claude_system = [
                    {"type": "text", "text": static_prompt, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": dynamic_context}
                ]

                async for event in _stream_claude_iteration(
                    llm, messages, claude_system, show_tools,
                    recent_logs, logs_this_turn
                ):
                    if event.get("_done"):
                        # Final response received
                        response_text = event.get("response_text", "")
                        new_exchange = finalize_turn(user_message, response_text, recent_logs, logs_this_turn)
                        session["recent_logs"] = recent_logs
                        session["last_exchange"] = new_exchange
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        return
                    elif event.get("_continue"):
                        # Tool calls processed, continue loop
                        messages = event["messages"]
                    else:
                        # Stream event to client
                        yield f"data: {json.dumps(event)}\n\n"
            else:
                # Generic provider (Gemini, OpenAI, etc.) - non-streaming
                system_prompt = (static_prompt, dynamic_context)
                response = llm.chat(messages, system_prompt, TOOLS, MAX_TOKENS)

                # Yield text content
                for block in response.content:
                    if block.get("type") == "text":
                        yield f"data: {json.dumps({'type': 'text', 'content': block['text']})}\n\n"

                # Yield usage if available
                if response.usage:
                    yield f"data: {json.dumps({'type': 'usage', **response.usage})}\n\n"

                if response.stop_reason == "tool_use":
                    # Add assistant message with tool calls
                    messages.append({"role": "assistant", "content": response.content})

                    # Execute tools
                    tool_results = []
                    for block in response.get_tool_calls():
                        tool_name = block["name"]
                        tool_input = block["input"]

                        if show_tools:
                            yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'input': tool_input})}\n\n"

                        result = execute_tool(tool_name, tool_input)

                        if show_tools:
                            display_result = result[:300] + "..." if len(result) > 300 else result
                            yield f"data: {json.dumps({'type': 'tool_result', 'name': tool_name, 'result': display_result})}\n\n"

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": result,
                        })

                        # Track for edit context
                        track_log_operation(tool_name, tool_input, result, recent_logs, logs_this_turn)

                    messages.append({"role": "user", "content": tool_results})
                else:
                    # Final response
                    response_text = response.get_text()
                    new_exchange = finalize_turn(user_message, response_text, recent_logs, logs_this_turn)
                    session["recent_logs"] = recent_logs
                    session["last_exchange"] = new_exchange
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

        # Safety: max iterations reached
        yield f"data: {json.dumps({'type': 'error', 'message': 'Max iterations reached'})}\n\n"

    except Exception as e:
        # Extract user-friendly error message
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
            error_msg = "Rate limit exceeded. Please wait a moment and try again."
        elif "401" in error_msg or "authentication" in error_msg.lower():
            error_msg = "API authentication failed. Please check your API key."
        elif "timeout" in error_msg.lower():
            error_msg = "Request timed out. Please try again."
        else:
            # Keep it short but informative
            error_msg = f"LLM error: {error_msg[:200]}"

        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"


async def _stream_claude_iteration(llm, messages, system_prompt, show_tools, recent_logs, logs_this_turn):
    """Handle one iteration of Claude streaming with tool execution."""
    import anthropic
    client = anthropic.Anthropic()

    current_text = ""

    with client.messages.stream(
        model=llm.model,
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
                        yield {"type": "tool_start", "name": event.content_block.name}

            elif event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    current_text += event.delta.text
                    yield {"type": "text", "content": event.delta.text}

            elif event.type == "content_block_stop":
                pass

        final_message = stream.get_final_message()

    # Yield usage
    if hasattr(final_message, 'usage') and final_message.usage:
        usage = final_message.usage
        yield {
            'type': 'usage',
            'input_tokens': usage.input_tokens,
            'output_tokens': usage.output_tokens,
            'cache_creation_input_tokens': getattr(usage, 'cache_creation_input_tokens', 0),
            'cache_read_input_tokens': getattr(usage, 'cache_read_input_tokens', 0),
        }

    if final_message.stop_reason == "tool_use":
        # Build assistant content
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

        messages.append({"role": "assistant", "content": assistant_content})

        # Execute tools
        tool_results = []
        for block in final_message.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                if show_tools:
                    yield {"type": "tool_call", "name": tool_name, "input": tool_input}

                result = execute_tool(tool_name, tool_input)

                if show_tools:
                    display_result = result[:300] + "..." if len(result) > 300 else result
                    yield {"type": "tool_result", "name": tool_name, "result": display_result}

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

                # Track for edit context
                track_log_operation(tool_name, tool_input, result, recent_logs, logs_this_turn)

        messages.append({"role": "user", "content": tool_results})

        # Signal to continue loop
        yield {"_continue": True, "messages": messages}
    else:
        # Final text response
        response_text = ""
        for block in final_message.content:
            if hasattr(block, "text"):
                response_text += block.text

        yield {"_done": True, "response_text": response_text}


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


@app.get("/api/config")
async def get_config(authenticated: bool = Depends(verify_credentials)):
    """Get current server configuration (provider, models)."""
    return {
        "provider": LLM_PROVIDER,
        "default_model": get_model_for_tier("default"),
        "smart_model": get_model_for_tier("smart"),
    }


@app.get("/api/profile")
async def get_profile(authenticated: bool = Depends(verify_credentials)):
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
