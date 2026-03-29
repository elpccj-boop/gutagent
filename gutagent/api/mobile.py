"""
Mobile API for GutAgent - Stateless LLM Proxy

Endpoints:
    POST /auth/register  - Create account
    POST /auth/login     - Get JWT token
    POST /chat           - Proxy to LLM (Claude/Gemini/OpenAI)
    POST /settings       - Update user's API key
    GET  /settings       - Get current settings

Environment variables (.env):
    JWT_SECRET       - Secret for signing tokens (required in production)
    ENCRYPTION_KEY   - Fernet key for encrypting API keys (required in production)
    MOBILE_DB_PATH   - Path to users database (default: ./data/mobile_users.db)

Health data stays on the phone. Server never sees it except in LLM context.
"""

import os
import secrets
import traceback
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
import jwt
import bcrypt
import sqlite3
from cryptography.fernet import Fernet

from gutagent.config import MODELS, MAX_TOKENS

# ============================================================
# GEMINI CACHE STORE (module-level, persists across requests)
# ============================================================

import hashlib
import time

# Key: hash of (model, system_prompt), Value: {"name": cache_name, "expires_at": timestamp}
_gemini_cache_store: dict[str, dict] = {}

# ============================================================
# CONVERSATION TOKEN TRACKER (tracks tokens across iterations)
# ============================================================

# Key: (user_email, question_hash), Value: {"tokens": {...}, "iterations": int}
_conversation_tracker: dict[tuple, dict] = {}

def _get_conversation_key(email: str, question: str) -> tuple:
    """Generate a key for tracking a conversation."""
    # Use first user question as conversation identifier
    q_hash = hashlib.md5(question.encode()).hexdigest()[:8]
    return (email, q_hash)

def _track_tokens(email: str, question: str, iteration: int, usage: dict) -> dict:
    """Track tokens for a conversation, return cumulative totals."""
    key = _get_conversation_key(email, question)

    if iteration == 1:
        # New conversation - reset tracker
        _conversation_tracker[key] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "iterations": 0,
        }

    tracker = _conversation_tracker.get(key, {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "iterations": 0,
    })

    # Add this iteration's tokens
    tracker["input_tokens"] += usage.get("input_tokens", 0)
    tracker["output_tokens"] += usage.get("output_tokens", 0)
    tracker["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
    tracker["cache_write_tokens"] += usage.get("cache_creation_input_tokens", 0)
    tracker["iterations"] = iteration

    _conversation_tracker[key] = tracker

    # Clean up old entries (keep last 100)
    if len(_conversation_tracker) > 100:
        oldest_keys = list(_conversation_tracker.keys())[:-100]
        for k in oldest_keys:
            del _conversation_tracker[k]

    return tracker
GEMINI_CACHE_TTL_SECONDS = 3600  # 1 hour (Gemini minimum)

# ============================================================
# CONFIG
# ============================================================

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    print(f"⚠️  No JWT_SECRET set. Generated temporary: {JWT_SECRET[:20]}...")
    print("   Set JWT_SECRET in .env for production!")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    print(f"⚠️  No ENCRYPTION_KEY set. Generated temporary: {ENCRYPTION_KEY[:20]}...")
    print("   Set ENCRYPTION_KEY in .env for production!")

fernet = Fernet(ENCRYPTION_KEY.encode())

DATABASE_PATH = os.getenv("MOBILE_DB_PATH", "./data/mobile_users.db")
# Ensure directory exists
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

# Cache TTL for Claude (default 5 min, can set to "1h" for 1 hour)
CLAUDE_CACHE_TTL = os.getenv("CLAUDE_CACHE_TTL")

# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            llm_provider TEXT DEFAULT 'claude',
            model_tier TEXT DEFAULT 'default',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        CREATE TABLE IF NOT EXISTS user_api_keys (
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            api_key_encrypted TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, provider),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()
    print(f"   Database: {DATABASE_PATH}")

# ============================================================
# AUTH HELPERS
# ============================================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: int, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

def encrypt_api_key(key: str) -> str:
    return fernet.encrypt(key.encode()).decode()

def decrypt_api_key(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()

# ============================================================
# FASTAPI APP
# ============================================================

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for startup/shutdown."""
    init_db()
    yield

app = FastAPI(title="GutAgent Mobile API", lifespan=lifespan)
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# AUTH DEPENDENCY
# ============================================================

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return decode_token(credentials.credentials)

# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    user_id: int
    email: str

class SettingsRequest(BaseModel):
    llm_provider: str = "claude"
    model_tier: str = "default"

class ApiKeyRequest(BaseModel):
    provider: str
    api_key: str

class SettingsResponse(BaseModel):
    llm_provider: str
    model_tier: str
    api_keys: dict[str, bool]  # provider -> has_key

class ChatRequest(BaseModel):
    messages: list[dict]
    system: str
    patient_data: str
    turn_context: str
    tools: list[dict]  # Tool definitions from app

class ChatResponse(BaseModel):
    content: list[dict]
    stop_reason: str
    usage: Optional[dict] = None

# ============================================================
# AUTH ENDPOINTS
# ============================================================

@app.post("/auth/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest):
    """Create a new user account."""
    conn = get_db()

    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?", 
        (request.email,)
    ).fetchone()
    
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    cursor = conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (request.email, hash_password(request.password))
    )
    user_id = cursor.lastrowid

    conn.execute(
        "INSERT INTO user_settings (user_id) VALUES (?)",
        (user_id,)
    )
    conn.commit()
    conn.close()
    
    print(f"   ✓ Registered: {request.email}")

    return AuthResponse(
        token=create_token(user_id, request.email),
        user_id=user_id,
        email=request.email,
    )

@app.post("/auth/login", response_model=AuthResponse)
def login(request: LoginRequest):
    """Login and get JWT token."""
    conn = get_db()
    
    user = conn.execute(
        "SELECT id, email, password_hash FROM users WHERE email = ?",
        (request.email,)
    ).fetchone()
    conn.close()
    
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    print(f"   ✓ Login: {request.email}")

    return AuthResponse(
        token=create_token(user["id"], user["email"]),
        user_id=user["id"],
        email=user["email"],
    )

# ============================================================
# SETTINGS ENDPOINTS
# ============================================================

@app.post("/settings")
def update_settings(request: SettingsRequest, user: dict = Depends(get_current_user)):
    """Update user's LLM provider and model tier."""
    conn = get_db()

    conn.execute("""
        INSERT INTO user_settings (user_id, llm_provider, model_tier, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET 
            llm_provider = excluded.llm_provider,
            model_tier = excluded.model_tier,
            updated_at = CURRENT_TIMESTAMP
    """, (user["user_id"], request.llm_provider, request.model_tier))
    conn.commit()
    conn.close()

    print(f"   ✓ Settings updated: {user['email']} → {request.llm_provider}/{request.model_tier}")

    return {"success": True}

@app.post("/settings/apikey")
def set_api_key(request: ApiKeyRequest, user: dict = Depends(get_current_user)):
    """Set API key for a specific provider."""
    conn = get_db()
    
    encrypted_key = encrypt_api_key(request.api_key)
    
    conn.execute("""
        INSERT INTO user_api_keys (user_id, provider, api_key_encrypted, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, provider) DO UPDATE SET 
            api_key_encrypted = excluded.api_key_encrypted,
            updated_at = CURRENT_TIMESTAMP
    """, (user["user_id"], request.provider, encrypted_key))
    conn.commit()
    conn.close()
    
    print(f"   ✓ API key set: {user['email']} → {request.provider}")

    return {"success": True}

@app.delete("/settings/apikey/{provider}")
def delete_api_key(provider: str, user: dict = Depends(get_current_user)):
    """Delete API key for a specific provider."""
    conn = get_db()

    conn.execute(
        "DELETE FROM user_api_keys WHERE user_id = ? AND provider = ?",
        (user["user_id"], provider)
    )
    conn.commit()
    conn.close()

    print(f"   ✓ API key deleted: {user['email']} → {provider}")

    return {"success": True}

@app.get("/settings", response_model=SettingsResponse)
def get_settings(user: dict = Depends(get_current_user)):
    """Get user's current settings."""
    conn = get_db()
    
    settings = conn.execute(
        "SELECT llm_provider, model_tier FROM user_settings WHERE user_id = ?",
        (user["user_id"],)
    ).fetchone()

    keys = conn.execute(
        "SELECT provider FROM user_api_keys WHERE user_id = ?",
        (user["user_id"],)
    ).fetchall()
    conn.close()
    
    api_keys = {row["provider"]: True for row in keys}

    return SettingsResponse(
        llm_provider=settings["llm_provider"] if settings else "claude",
        model_tier=settings["model_tier"] if settings else "default",
        api_keys=api_keys,
    )

# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    """Simple health check."""
    return {"status": "ok"}

# ============================================================
# CHAT ENDPOINT
# ============================================================

def _prepend_dynamic_context(messages: list, patient_data: str, turn_context: str) -> list:
    """
    Prepend patient_data + turn_context to the first user message.

    Used for Gemini/OpenAI where we can only cache the system prompt,
    so dynamic context must go in user message (not cached, but keeps
    system prompt stable for caching).

    Mirrors CLI/Web's server.py _stream_generic_iteration() behavior.
    """
    dynamic_context = f"{patient_data}\n\n{turn_context}"

    if not dynamic_context.strip():
        return messages

    messages_with_context = []
    context_added = False

    for msg in messages:
        if msg["role"] == "user" and not context_added:
            content = msg["content"]
            if isinstance(content, str):
                # Wrap in clear tags so the model understands the structure
                content = f"[Current Context]\n{dynamic_context}\n\n[User Message]\n{content}"
                messages_with_context.append({"role": "user", "content": content})
                context_added = True
            else:
                # Content is list (tool_result), add as-is
                messages_with_context.append(msg)
        else:
            messages_with_context.append(msg)

    return messages_with_context


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """Proxy chat request to LLM."""

    # Find the CURRENT question being processed
    # Walk backwards: skip tool_results, find the last actual user text message
    current_question = ""
    iteration_in_turn = 1

    for i, msg in enumerate(reversed(request.messages)):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                # This is a text question - this is what we're answering
                current_question = content[:100] + ("..." if len(content) > 100 else "")
                # Count how many messages after this = iteration count
                # Each tool round = 2 messages (assistant tool_use + user tool_result)
                messages_after = i  # i is distance from end
                iteration_in_turn = 1 + (messages_after // 2)
                break
            elif isinstance(content, list):
                # Tool result - keep looking backwards
                continue

    print(f"\n{'='*60}")
    print(f"CHAT REQUEST from {user['email']}")
    print(f"  Question: {current_question}")
    print(f"  Iteration: {iteration_in_turn} | Messages: {len(request.messages)} | Tools: {len(request.tools)}")
    print(f"  System: {len(request.system)} | Patient: {len(request.patient_data)} | Turn: {len(request.turn_context)} chars")
    print(f"{'='*60}")

    conn = get_db()

    settings = conn.execute(
        "SELECT llm_provider, model_tier FROM user_settings WHERE user_id = ?",
        (user["user_id"],)
    ).fetchone()

    provider = settings["llm_provider"] if settings else "claude"
    model_tier = settings["model_tier"] if settings else "default"

    api_key_row = conn.execute(
        "SELECT api_key_encrypted FROM user_api_keys WHERE user_id = ? AND provider = ?",
        (user["user_id"], provider)
    ).fetchone()
    conn.close()
    
    if not api_key_row:
        raise HTTPException(
            status_code=400,
            detail=f"No API key configured for {provider}. Go to Settings → API Keys."
        )

    try:
        api_key = decrypt_api_key(api_key_row["api_key_encrypted"])
    except Exception as e:
        print(f"   ✗ Decryption failed: {e}")
        raise HTTPException(
            status_code=400,
            detail="API key decryption failed. Please re-enter your API key in Settings."
        )

    print(f"   → {MODELS[provider][model_tier]}")

    try:
        response = None
        if provider == "claude":
            response = await _call_claude(
                api_key,
                request.messages,
                request.system,      # Static prompt (cached)
                request.patient_data, # Patient data (cached)
                request.turn_context, # Turn context (not cached)
                model_tier,
                request.tools
            )
        elif provider == "gemini":
            # Gemini: cache ONLY static system prompt
            # Move patient_data + turn_context to user message
            messages_with_context = _prepend_dynamic_context(
                request.messages,
                request.patient_data,
                request.turn_context
            )
            response = await _call_gemini(
                api_key,
                messages_with_context,
                request.system,  # Only static prompt (cached via caches.create)
                model_tier,
                request.tools
            )
        elif provider == "openai":
            # OpenAI: cache ONLY static system prompt (automatic prefix caching)
            # Move patient_data + turn_context to user message
            messages_with_context = _prepend_dynamic_context(
                request.messages,
                request.patient_data,
                request.turn_context
            )
            response = await _call_openai(
                api_key,
                messages_with_context,
                request.system,  # Only static prompt (auto-cached if prefix matches)
                model_tier,
                request.tools
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

        # Track cumulative tokens
        if response and response.usage:
            cumulative = _track_tokens(user['email'], current_question, iteration_in_turn, response.usage)

            # Print token summary when conversation is done (end_turn)
            if response.stop_reason == "end_turn":
                in_tok = cumulative['input_tokens']
                out_tok = cumulative['output_tokens']
                cache_r = cumulative['cache_read_tokens']
                cache_w = cumulative['cache_write_tokens']
                iters = cumulative['iterations']

                # Build cache info string
                cache_parts = []
                if cache_r > 0:
                    cache_parts.append(f"{cache_r} read")
                if cache_w > 0:
                    cache_parts.append(f"{cache_w} write")
                cache_info = f" | cache: {', '.join(cache_parts)}" if cache_parts else ""

                iter_info = f" ({iters} iterations)" if iters > 1 else ""
                print(f"   TOTAL{iter_info}: in={in_tok} out={out_tok}{cache_info}")

        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"   ✗ LLM error ({provider}):")
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")


# ============================================================
# STREAMING CHAT ENDPOINT
# ============================================================

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Stream chat response via Server-Sent Events.

    Event types sent to client:
    - {"type": "text", "content": "..."} — Text chunk
    - {"type": "tool_start", "name": "...", "id": "..."} — Tool call starting
    - {"type": "tool_input", "content": "..."} — Tool input JSON chunk
    - {"type": "tool_use", "id": "...", "name": "...", "input": {...}} — Complete tool call
    - {"type": "usage", "input_tokens": N, ...} — Token usage
    - {"type": "done", "stop_reason": "..."} — Stream complete
    - {"type": "error", "message": "..."} — Error occurred

    When client receives tool_use events, it should:
    1. Execute tools locally
    2. Call /chat/stream again with tool_result messages
    """
    return StreamingResponse(
        _stream_chat(request, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def _stream_chat(request: ChatRequest, user: dict) -> AsyncGenerator[str, None]:
    """Generate SSE events for streaming chat."""
    print(f"\n{'='*60}")
    print(f"STREAM REQUEST from {user['email']}")
    print(f"  Messages: {len(request.messages)}")
    print(f"  Tools: {len(request.tools)}")
    print(f"{'='*60}")

    conn = get_db()

    settings = conn.execute(
        "SELECT llm_provider, model_tier FROM user_settings WHERE user_id = ?",
        (user["user_id"],)
    ).fetchone()

    provider = settings["llm_provider"] if settings else "claude"
    model_tier = settings["model_tier"] if settings else "default"

    api_key_row = conn.execute(
        "SELECT api_key_encrypted FROM user_api_keys WHERE user_id = ? AND provider = ?",
        (user["user_id"], provider)
    ).fetchone()
    conn.close()

    if not api_key_row:
        yield f"data: {json.dumps({'type': 'error', 'message': f'No API key configured for {provider}'})}\n\n"
        return

    try:
        api_key = decrypt_api_key(api_key_row["api_key_encrypted"])
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': 'API key decryption failed'})}\n\n"
        return

    print(f"   → Stream: {user['email']} via {provider}/{model_tier}")

    try:
        if provider == "claude":
            async for event in _stream_claude(
                api_key,
                request.messages,
                request.system,
                request.patient_data,
                request.turn_context,
                model_tier,
                request.tools
            ):
                yield f"data: {json.dumps(event)}\n\n"
        elif provider == "gemini":
            messages_with_context = _prepend_dynamic_context(
                request.messages,
                request.patient_data,
                request.turn_context
            )
            async for event in _stream_gemini(
                api_key,
                messages_with_context,
                request.system,
                model_tier,
                request.tools
            ):
                yield f"data: {json.dumps(event)}\n\n"
        elif provider == "openai":
            messages_with_context = _prepend_dynamic_context(
                request.messages,
                request.patient_data,
                request.turn_context
            )
            async for event in _stream_openai(
                api_key,
                messages_with_context,
                request.system,
                model_tier,
                request.tools
            ):
                yield f"data: {json.dumps(event)}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Unknown provider: {provider}'})}\n\n"
    except Exception as e:
        print(f"   ✗ Stream error ({provider}):")
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"


# ============================================================
# LLM PROVIDERS (BLOCKING)
# ============================================================

async def _call_claude(
    api_key: str,
    messages: list,
    system: str,
    patient_data: str,
    turn_context: str,
    model_tier: str,
    tools: list
) -> ChatResponse:
    """
    Call Claude API with three-tier prompt caching.

    Cache structure:
    - system (static): Instructions + profile — CACHED
    - patient_data: Recent health data — CACHED (separate breakpoint)
    - turn_context: Timestamp + recent logs — NOT CACHED
    """
    import anthropic
    
    client = anthropic.Anthropic(api_key=api_key)
    model = MODELS["claude"][model_tier]

    print(f"      Model: {model}")
    print(f"      Messages: {len(messages)}")
    print(f"      Tools: {len(tools)}")

    # Build cache_control based on TTL setting
    if CLAUDE_CACHE_TTL:
        cache_control = {"type": "ephemeral", "ttl": CLAUDE_CACHE_TTL}
    else:
        cache_control = {"type": "ephemeral"}

    # Three-tier system prompt - only include non-empty blocks with cache_control
    cached_system = []
    if system:
        cached_system.append({"type": "text", "text": system, "cache_control": cache_control})
    if patient_data:
        cached_system.append({"type": "text", "text": patient_data, "cache_control": cache_control})
    if turn_context:
        cached_system.append({"type": "text", "text": turn_context})

    # Fallback if all empty
    if not cached_system:
        cached_system.append({"type": "text", "text": "You are a helpful assistant."})

    # Cache tools (mark last tool)
    cached_tools = tools.copy()
    if cached_tools:
        cached_tools[-1] = {
            **cached_tools[-1],
            "cache_control": cache_control
        }

    print(f"      System blocks: {len(cached_system)}")

    # Build kwargs - only include tools if present
    create_kwargs = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": cached_system,
        "messages": messages,
    }
    if cached_tools:
        create_kwargs["tools"] = cached_tools

    response = client.messages.create(**create_kwargs)
    
    print(f"      ✓ Response: {response.stop_reason}")
    if response.usage:
        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        cache_read = getattr(response.usage, 'cache_read_input_tokens', 0)
        cache_create = getattr(response.usage, 'cache_creation_input_tokens', 0)
        if cache_create > 0:
            print(f"      Tokens: in={in_tok} out={out_tok} cache_create={cache_create}")
        else:
            print(f"      Tokens: in={in_tok} out={out_tok} cache_read={cache_read}")

    # Log what we're returning (ALL blocks)
    tool_count = 0
    for block in response.content:
        if hasattr(block, 'type'):
            if block.type == 'tool_use':
                tool_count += 1
                print(f"      → Tool {tool_count}: {block.name}")
            elif block.type == 'text':
                print(f"      → Text: {block.text[:100]}...")

    return ChatResponse(
        content=[block.model_dump() for block in response.content],  # ALL blocks
        stop_reason=response.stop_reason,
        usage={
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_input_tokens": getattr(response.usage, 'cache_read_input_tokens', 0),
            "cache_creation_input_tokens": getattr(response.usage, 'cache_creation_input_tokens', 0),
        } if response.usage else None,
    )

async def _call_gemini(api_key: str, messages: list, system: str, model_tier: str, tools: list) -> ChatResponse:
    """
    Call Gemini API with explicit context caching.

    Gemini requires explicit cache creation via client.caches.create().
    Cache is stored module-level and reused for 1 hour.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    model_name = MODELS["gemini"][model_tier]

    # Try to get or create cache for system prompt
    cache_name, cache_creation_tokens = _get_or_create_gemini_cache(
        client, types, model_name, system, tools
    )

    # Convert messages to Gemini format
    gemini_messages = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        content = msg["content"]

        if isinstance(content, str):
            gemini_messages.append({"role": role, "parts": [{"text": content}]})
        elif isinstance(content, list):
            parts = []
            for block in content:
                if block.get("type") == "text":
                    parts.append({"text": block["text"]})
                elif block.get("type") == "tool_use":
                    parts.append({
                        "function_call": {
                            "name": block["name"],
                            "args": block["input"],
                        }
                    })
                elif block.get("type") == "tool_result":
                    gemini_messages.append({
                        "role": "user",
                        "parts": [{
                            "function_response": {
                                "name": block.get("tool_use_id", "").replace("gemini_", "").split("_")[0],
                                "response": {"result": block["content"]},
                            }
                        }]
                    })
                    continue
            if parts:
                gemini_messages.append({"role": role, "parts": parts})

    # Build config based on whether we have a cache
    config_kwargs = {}

    if cache_name:
        print(f"      Using cache: {cache_name[:30]}...")
        config_kwargs["cached_content"] = cache_name
    else:
        # No cache - include system instruction and tools directly
        if system:
            config_kwargs["system_instruction"] = system
        if tools:
            function_declarations = []
            for tool in tools:
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                })
            config_kwargs["tools"] = [{"function_declarations": function_declarations}]

    response = client.models.generate_content(
        model=model_name,
        contents=gemini_messages,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    # Log token usage
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        um = response.usage_metadata
        total_input = getattr(um, 'prompt_token_count', 0) or 0
        cached_tokens = getattr(um, 'cached_content_token_count', 0) or 0
        out_tok = getattr(um, 'candidates_token_count', 0) or 0
        if cache_creation_tokens > 0:
            print(f"      ✓ Response | Tokens: in={total_input - cached_tokens} out={out_tok} cache_create={cache_creation_tokens}")
        else:
            print(f"      ✓ Response | Tokens: in={total_input - cached_tokens} out={out_tok} cache_read={cached_tokens}")
    else:
        print(f"      ✓ Response received")

    # Process ALL parts
    if response.candidates and response.candidates[0].content.parts:
        content_blocks = []
        has_function_call = False

        for i, part in enumerate(response.candidates[0].content.parts):
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                print(f"      → Function call: {fc.name}")
                content_blocks.append({
                    "type": "tool_use",
                    "id": f"gemini_{fc.name}_{i}",
                    "name": fc.name,
                    "input": dict(fc.args) if fc.args else {},
                })
                has_function_call = True
            elif hasattr(part, 'text') and part.text:
                print(f"      → Text: {part.text[:100]}...")
                content_blocks.append({
                    "type": "text",
                    "text": part.text
                })

        if content_blocks:
            # Build usage with cache info
            usage = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                um = response.usage_metadata
                total_input = getattr(um, 'prompt_token_count', 0) or 0
                cached_tokens = getattr(um, 'cached_content_token_count', 0) or 0
                uncached_input = total_input - cached_tokens

                usage = {
                    "input_tokens": uncached_input,
                    "output_tokens": getattr(um, 'candidates_token_count', 0) or 0,
                }

                # Report cache_creation OR cache_read
                if cache_creation_tokens > 0:
                    usage["cache_creation_input_tokens"] = cache_creation_tokens
                elif cached_tokens > 0:
                    usage["cache_read_input_tokens"] = cached_tokens

            return ChatResponse(
                content=content_blocks,
                stop_reason="tool_use" if has_function_call else "end_turn",
                usage=usage,
            )

    # Fallback
    text = response.text if hasattr(response, 'text') else str(response)
    print(f"      → Fallback text: {text[:100]}...")
    return ChatResponse(
        content=[{"type": "text", "text": text}],
        stop_reason="end_turn",
    )


def _get_or_create_gemini_cache(client, types, model: str, system_prompt: str, tools: list) -> tuple:
    """
    Get existing cache or create new one for Gemini.

    Returns:
        Tuple of (cache_name, cache_creation_tokens)
    """
    global _gemini_cache_store

    # Generate cache key from model + system prompt
    content = f"{model}:{system_prompt}"
    cache_key = hashlib.sha256(content.encode()).hexdigest()[:16]
    now = time.time()

    # Check for valid cached entry
    if cache_key in _gemini_cache_store:
        entry = _gemini_cache_store[cache_key]
        if entry["expires_at"] > now:
            return entry["name"], 0  # Cache hit
        else:
            # Cache expired, clean up
            try:
                client.caches.delete(name=entry["name"])
            except Exception:
                pass
            del _gemini_cache_store[cache_key]

    # Create new cache
    try:
        cache_config = {
            "system_instruction": system_prompt,
            "ttl": f"{GEMINI_CACHE_TTL_SECONDS}s",
            "display_name": f"gutagent-mobile-{cache_key}",
        }

        # Add tools to cache if present
        if tools:
            function_declarations = []
            for tool in tools:
                function_declarations.append(
                    types.FunctionDeclaration(
                        name=tool["name"],
                        description=tool.get("description", ""),
                        parameters=tool.get("input_schema", {}),
                    )
                )
            cache_config["tools"] = [types.Tool(function_declarations=function_declarations)]

        cache = client.caches.create(
            model=model,
            config=types.CreateCachedContentConfig(**cache_config),
        )

        # Get token count from cache creation
        cache_tokens = 0
        if hasattr(cache, 'usage_metadata') and cache.usage_metadata:
            cache_tokens = getattr(cache.usage_metadata, 'total_token_count', 0) or 0

        # Store cache reference
        _gemini_cache_store[cache_key] = {
            "name": cache.name,
            "expires_at": now + GEMINI_CACHE_TTL_SECONDS - 60,  # Buffer
        }

        print(f"      Created Gemini cache: {cache.name[:30]}... ({cache_tokens} tokens)")
        return cache.name, cache_tokens

    except Exception as e:
        print(f"      Gemini caching failed: {e} (falling back to non-cached)")
        return None, 0

async def _call_openai(api_key: str, messages: list, system: str, model_tier: str, tools: list) -> ChatResponse:
    """
    Call OpenAI API with automatic prefix caching.

    OpenAI uses automatic caching (no explicit API calls needed):
    - Prompts ≥1024 tokens are eligible
    - Cache hits reduce latency by ~80% and costs by ~50%
    - We keep static content first to maximize cache hits
    - Cache info returned in prompt_tokens_details.cached_tokens
    """
    from openai import OpenAI
    import json

    client = OpenAI(api_key=api_key)
    model = MODELS["openai"][model_tier]

    print(f"      Model: {model}")

    # Build OpenAI messages - system prompt FIRST for cache prefix matching
    openai_messages = [{"role": "system", "content": system}]

    for msg in messages:
        content = msg["content"]

        if isinstance(content, str):
            openai_messages.append({"role": msg["role"], "content": content})
        elif isinstance(content, list):
            # Handle structured content
            for block in content:
                if block.get("type") == "tool_use":
                    # Assistant's tool call
                    openai_messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            }
                        }]
                    })
                elif block.get("type") == "tool_result":
                    # User's tool result
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block["content"],
                    })

    # Convert tools to OpenAI format
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        })

    print(f"      OpenAI messages: {len(openai_messages)}")
    print(f"      Tools: {len(openai_tools)}")

    # Build kwargs - only include tools if present
    create_kwargs = {
        "model": model,
        "messages": openai_messages,
    }
    if openai_tools:
        create_kwargs["tools"] = openai_tools

    response = client.chat.completions.create(**create_kwargs)
    
    # Log token usage
    if response.usage:
        total_input = response.usage.prompt_tokens or 0
        out_tok = response.usage.completion_tokens or 0
        cached = 0
        if hasattr(response.usage, 'prompt_tokens_details') and response.usage.prompt_tokens_details:
            cached = getattr(response.usage.prompt_tokens_details, 'cached_tokens', 0) or 0
        print(f"      ✓ Response | Tokens: in={total_input - cached} out={out_tok} cache_read={cached}")
    else:
        print(f"      ✓ Response received")

    message = response.choices[0].message

    # Build usage with cache info (OpenAI automatic caching)
    usage = None
    if response.usage:
        total_input = response.usage.prompt_tokens or 0
        cached = 0

        # OpenAI returns cached_tokens in prompt_tokens_details
        if hasattr(response.usage, 'prompt_tokens_details') and response.usage.prompt_tokens_details:
            cached = getattr(response.usage.prompt_tokens_details, 'cached_tokens', 0) or 0

        usage = {
            "input_tokens": total_input - cached,  # Uncached only (matches Claude semantics)
            "output_tokens": response.usage.completion_tokens or 0,
        }

        if cached > 0:
            usage["cache_read_input_tokens"] = cached
            print(f"      Cache hit: {cached} tokens")

    # Return ALL tool calls
    if message.tool_calls:
        content_blocks = []
        for i, tc in enumerate(message.tool_calls):
            print(f"      → Tool call {i+1}: {tc.function.name}")
            content_blocks.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": json.loads(tc.function.arguments),
            })

        return ChatResponse(
            content=content_blocks,
            stop_reason="tool_use",
            usage=usage,
        )

    # Text response
    print(f"      → Text: {message.content[:100] if message.content else '(empty)'}...")
    return ChatResponse(
        content=[{"type": "text", "text": message.content or ""}],
        stop_reason="end_turn",
        usage=usage,
    )


# ============================================================
# LLM PROVIDERS (STREAMING)
# ============================================================

async def _stream_claude(
    api_key: str,
    messages: list,
    system: str,
    patient_data: str,
    turn_context: str,
    model_tier: str,
    tools: list
) -> AsyncGenerator[dict, None]:
    """Stream Claude response with three-tier caching."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    model = MODELS["claude"][model_tier]

    # Build cache_control
    if CLAUDE_CACHE_TTL:
        cache_control = {"type": "ephemeral", "ttl": CLAUDE_CACHE_TTL}
    else:
        cache_control = {"type": "ephemeral"}

    # Three-tier system prompt - only include non-empty blocks with cache_control
    cached_system = []
    if system:
        cached_system.append({"type": "text", "text": system, "cache_control": cache_control})
    if patient_data:
        cached_system.append({"type": "text", "text": patient_data, "cache_control": cache_control})
    if turn_context:
        cached_system.append({"type": "text", "text": turn_context})

    # Fallback if all empty
    if not cached_system:
        cached_system.append({"type": "text", "text": "You are a helpful assistant."})

    # Cache tools
    cached_tools = tools.copy()
    if cached_tools:
        cached_tools[-1] = {**cached_tools[-1], "cache_control": cache_control}

    print(f"      Streaming Claude: {model}")

    # Build kwargs - only include tools if present
    stream_kwargs = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": cached_system,
        "messages": messages,
    }
    if cached_tools:
        stream_kwargs["tools"] = cached_tools

    with client.messages.stream(**stream_kwargs) as stream:
        for event in stream:
            if event.type == "content_block_start":
                if event.content_block.type == "tool_use":
                    yield {"type": "tool_start", "name": event.content_block.name, "id": event.content_block.id}

            elif event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    yield {"type": "text", "content": event.delta.text}
                elif event.delta.type == "input_json_delta":
                    yield {"type": "tool_input", "content": event.delta.partial_json}

        # Get final message
        final = stream.get_final_message()

        # Send complete tool_use blocks
        for block in final.content:
            if block.type == "tool_use":
                yield {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                }

        # Send usage
        if final.usage:
            yield {
                "type": "usage",
                "input_tokens": final.usage.input_tokens,
                "output_tokens": final.usage.output_tokens,
                "cache_read_input_tokens": getattr(final.usage, 'cache_read_input_tokens', 0),
                "cache_creation_input_tokens": getattr(final.usage, 'cache_creation_input_tokens', 0),
            }

        yield {"type": "done", "stop_reason": final.stop_reason}


async def _stream_gemini(
    api_key: str,
    messages: list,
    system: str,
    model_tier: str,
    tools: list
) -> AsyncGenerator[dict, None]:
    """Stream Gemini response with explicit caching."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    model_name = MODELS["gemini"][model_tier]

    # Get or create cache
    cache_name, cache_creation_tokens = _get_or_create_gemini_cache(
        client, types, model_name, system, tools
    )

    # Convert messages to Gemini format
    gemini_messages = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        content = msg["content"]

        if isinstance(content, str):
            gemini_messages.append({"role": role, "parts": [{"text": content}]})
        elif isinstance(content, list):
            parts = []
            for block in content:
                if block.get("type") == "text":
                    parts.append({"text": block["text"]})
                elif block.get("type") == "tool_use":
                    parts.append({
                        "function_call": {
                            "name": block["name"],
                            "args": block["input"],
                        }
                    })
                elif block.get("type") == "tool_result":
                    gemini_messages.append({
                        "role": "user",
                        "parts": [{
                            "function_response": {
                                "name": block.get("tool_use_id", "").replace("gemini_", "").split("_")[0],
                                "response": {"result": block["content"]},
                            }
                        }]
                    })
                    continue
            if parts:
                gemini_messages.append({"role": role, "parts": parts})

    # Build config
    config_kwargs = {}
    if cache_name:
        config_kwargs["cached_content"] = cache_name
    else:
        if system:
            config_kwargs["system_instruction"] = system
        if tools:
            function_declarations = [
                {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}
                for t in tools
            ]
            config_kwargs["tools"] = [{"function_declarations": function_declarations}]

    print(f"      Streaming Gemini: {model_name}")

    # Use streaming API
    collected_text = ""
    collected_tool_calls = []
    usage = None

    for chunk in client.models.generate_content_stream(
        model=model_name,
        contents=gemini_messages,
        config=types.GenerateContentConfig(**config_kwargs),
    ):
        # Extract usage from final chunk
        if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
            um = chunk.usage_metadata
            total_input = getattr(um, 'prompt_token_count', 0) or 0
            cached_tokens = getattr(um, 'cached_content_token_count', 0) or 0

            usage = {
                "input_tokens": total_input - cached_tokens,
                "output_tokens": getattr(um, 'candidates_token_count', 0) or 0,
            }
            if cache_creation_tokens > 0:
                usage["cache_creation_input_tokens"] = cache_creation_tokens
            elif cached_tokens > 0:
                usage["cache_read_input_tokens"] = cached_tokens

        if not chunk.candidates or not chunk.candidates[0].content:
            continue

        parts = chunk.candidates[0].content.parts
        if not parts:
            continue

        for part in parts:
            if hasattr(part, 'text') and part.text:
                collected_text += part.text
                yield {"type": "text", "content": part.text}
            elif hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                tool_call = {
                    "type": "tool_use",
                    "id": f"gemini_{fc.name}_{len(collected_tool_calls)}",
                    "name": fc.name,
                    "input": dict(fc.args) if fc.args else {},
                }
                collected_tool_calls.append(tool_call)
                yield {"type": "tool_start", "name": fc.name, "id": tool_call["id"]}

    # Send complete tool_use blocks
    for tc in collected_tool_calls:
        yield tc

    # Send usage
    if usage:
        yield {"type": "usage", **usage}

    stop_reason = "tool_use" if collected_tool_calls else "end_turn"
    yield {"type": "done", "stop_reason": stop_reason}


async def _stream_openai(
    api_key: str,
    messages: list,
    system: str,
    model_tier: str,
    tools: list
) -> AsyncGenerator[dict, None]:
    """Stream OpenAI response with automatic prefix caching."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    model = MODELS["openai"][model_tier]

    # Build OpenAI messages
    openai_messages = [{"role": "system", "content": system}]

    for msg in messages:
        content = msg["content"]

        if isinstance(content, str):
            openai_messages.append({"role": msg["role"], "content": content})
        elif isinstance(content, list):
            for block in content:
                if block.get("type") == "tool_use":
                    openai_messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            }
                        }]
                    })
                elif block.get("type") == "tool_result":
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block["content"],
                    })

    # Convert tools
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]

    print(f"      Streaming OpenAI: {model}")

    # Streaming request - only include tools if present
    current_tool_calls = {}
    current_text = ""
    usage = None

    stream_kwargs = {
        "model": model,
        "messages": openai_messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if openai_tools:
        stream_kwargs["tools"] = openai_tools

    stream = client.chat.completions.create(**stream_kwargs)

    for chunk in stream:
        # Extract usage from final chunk
        if hasattr(chunk, 'usage') and chunk.usage:
            total_input = chunk.usage.prompt_tokens or 0
            cached = 0
            if hasattr(chunk.usage, 'prompt_tokens_details') and chunk.usage.prompt_tokens_details:
                cached = getattr(chunk.usage.prompt_tokens_details, 'cached_tokens', 0) or 0

            usage = {
                "input_tokens": total_input - cached,
                "output_tokens": chunk.usage.completion_tokens or 0,
            }
            if cached > 0:
                usage["cache_read_input_tokens"] = cached

        delta = chunk.choices[0].delta if chunk.choices else None
        if not delta:
            continue

        # Text content
        if delta.content:
            current_text += delta.content
            yield {"type": "text", "content": delta.content}

        # Tool calls
        if delta.tool_calls:
            for tool_call in delta.tool_calls:
                idx = tool_call.index
                if idx not in current_tool_calls:
                    current_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}

                if tool_call.id:
                    current_tool_calls[idx]["id"] = tool_call.id

                if tool_call.function:
                    if tool_call.function.name:
                        current_tool_calls[idx]["name"] = tool_call.function.name
                        yield {"type": "tool_start", "name": tool_call.function.name, "id": current_tool_calls[idx]["id"]}
                    if tool_call.function.arguments:
                        current_tool_calls[idx]["arguments"] += tool_call.function.arguments
                        yield {"type": "tool_input", "content": tool_call.function.arguments}

    # Send complete tool_use blocks
    for idx in sorted(current_tool_calls.keys()):
        tc = current_tool_calls[idx]
        try:
            args = json.loads(tc["arguments"]) if tc["arguments"] else {}
        except json.JSONDecodeError:
            args = {}
        yield {
            "type": "tool_use",
            "id": tc["id"],
            "name": tc["name"],
            "input": args,
        }

    # Send usage
    if usage:
        yield {"type": "usage", **usage}

    stop_reason = "tool_use" if current_tool_calls else "end_turn"
    yield {"type": "done", "stop_reason": stop_reason}


# ============================================================
# MAIN
# ============================================================

def main():
    import uvicorn
    
    print("\n📱 GutAgent Mobile API")
    print(f"   http://localhost:8001")
    print(f"\n   Endpoints:")
    print(f"   POST /auth/register")
    print(f"   POST /auth/login")
    print(f"   GET  /settings")
    print(f"   POST /settings")
    print(f"   POST /chat")
    print(f"   POST /chat/stream")
    print(f"\n   Press Ctrl+C to stop\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")

if __name__ == "__main__":
    main()
