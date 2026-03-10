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
from gutagent.prompts.system import build_system_prompt
from gutagent.tools.registry import execute_tool
from gutagent.llm import get_provider


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

# Session storage (in-memory for now — resets on server restart)
# For persistence, you'd store in SQLite or Redis
sessions: dict[str, list] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    model: str = "default"  # "default" (fast/cheap) or "smart" (capable)
    show_tools: bool = False


def get_model(tier: str) -> str:
    """Get model string for the current provider and tier."""
    return get_model_for_tier(tier)


async def run_agent_streaming(
    user_message: str,
    conversation_history: list,
    profile: dict,
    model: str,
    show_tools: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Streaming version of the agent loop.
    Yields Server-Sent Events as Claude generates responses.
    """
    import anthropic
    client = anthropic.Anthropic()

    system_prompt = build_system_prompt(profile)

    # Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_message,
    })
    
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Stream from Claude
        collected_content = []
        current_text = ""
        tool_uses = []

        with client.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=TOOLS,
            messages=conversation_history,
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
                        collected_content.append({"type": "text", "text": current_text})
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

            conversation_history.append({
                "role": "assistant",
                "content": assistant_content,
            })
            
            # Execute tools
            tool_results = []
            for block in final_message.content:
                if block.type == "tool_use":
                    if show_tools:
                        yield f"data: {json.dumps({'type': 'tool_call', 'name': block.name, 'input': block.input})}\n\n"

                    result = execute_tool(block.name, block.input)

                    if show_tools:
                        # Truncate for display
                        display_result = result[:300] + "..." if len(result) > 300 else result
                        yield f"data: {json.dumps({'type': 'tool_result', 'name': block.name, 'result': display_result})}\n\n"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            
            # Add tool results to history
            conversation_history.append({
                "role": "user",
                "content": tool_results,
            })
            
            # Continue loop
        else:
            # Final text response — add to history
            text_parts = []
            for block in final_message.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)

            assistant_message = "\n".join(text_parts)
            conversation_history.append({
                "role": "assistant",
                "content": assistant_message,
            })
            
            # Signal end of stream
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
    
    # Safety: max iterations reached
    yield f"data: {json.dumps({'type': 'error', 'message': 'Max iterations reached'})}\n\n"


@app.post("/api/chat")
async def chat(request: ChatRequest, authenticated: bool = Depends(verify_credentials)):
    """Stream a chat response."""
    profile = load_profile()
    
    # Get or create session
    if request.session_id not in sessions:
        sessions[request.session_id] = []
    
    history = sessions[request.session_id]
    model = get_model(request.model)
    
    return StreamingResponse(
        run_agent_streaming(
            user_message=request.message,
            conversation_history=history,
            profile=profile,
            model=model,
            show_tools=request.show_tools,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/clear")
async def clear_session(request: Request, authenticated: bool = Depends(verify_credentials)):
    """Clear conversation history for a session."""
    data = await request.json()
    session_id = data.get("session_id", "default")
    if session_id in sessions:
        sessions[session_id] = []
    return {"status": "cleared"}


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
