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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import jwt
import bcrypt
import sqlite3
from cryptography.fernet import Fernet

from gutagent.config import MODELS, MAX_TOKENS

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

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """Proxy chat request to LLM."""
    print(f"\n{'='*60}")
    print(f"CHAT REQUEST from {user['email']}")
    print(f"  Messages: {len(request.messages)}")
    print(f"  Tools: {len(request.tools)}")
    print(f"  System prompt: {len(request.system)} chars")
    print(f"  Patient data: {len(request.patient_data)} chars")
    print(f"  Turn context: {len(request.turn_context)} chars")
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

    full_system = f"{request.system}\n\n{request.patient_data}\n\n{request.turn_context}"
    
    print(f"   → Chat: {user['email']} via {provider}/{model_tier}")

    try:
        if provider == "claude":
            return await _call_claude(api_key, request.messages, full_system, model_tier, request.tools)
        elif provider == "gemini":
            return await _call_gemini(api_key, request.messages, full_system, model_tier, request.tools)
        elif provider == "openai":
            return await _call_openai(api_key, request.messages, full_system, model_tier, request.tools)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"   ✗ LLM error ({provider}):")
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")

# ============================================================
# LLM PROVIDERS
# ============================================================

async def _call_claude(api_key: str, messages: list, system: str, model_tier: str, tools: list) -> ChatResponse:
    """Call Claude API."""
    import anthropic
    
    client = anthropic.Anthropic(api_key=api_key)
    model = MODELS["claude"][model_tier]

    print(f"      Model: {model}")
    print(f"      Messages: {len(messages)}")
    print(f"      Tools: {len(tools)}")
    print(f"      System prompt: {len(system)} chars")

    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
        tools=tools,
    )
    
    print(f"      ✓ Response: {response.stop_reason}")
    if response.usage:
        print(f"      Tokens: in={response.usage.input_tokens} out={response.usage.output_tokens}")

    # Log what we're returning
    for block in response.content:
        if hasattr(block, 'type'):
            if block.type == 'tool_use':
                print(f"      → Tool: {block.name}")
            elif block.type == 'text':
                print(f"      → Text: {block.text[:100]}...")

    return ChatResponse(
        content=[block.model_dump() for block in response.content],
        stop_reason=response.stop_reason,
        usage={
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        } if response.usage else None,
    )

async def _call_gemini(api_key: str, messages: list, system: str, model_tier: str, tools: list) -> ChatResponse:
    """Call Gemini API."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    model_name = MODELS["gemini"][model_tier]

    print(f"      Model: {model_name}")
    print(f"      Messages: {len(messages)}")

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
                    # Model's function call
                    parts.append({
                        "function_call": {
                            "name": block["name"],
                            "args": block["input"],
                        }
                    })
                elif block.get("type") == "tool_result":
                    # User's function response - Gemini expects this as a separate message
                    # with role "user" containing function_response
                    gemini_messages.append({
                        "role": "user",
                        "parts": [{
                            "function_response": {
                                "name": block.get("tool_use_id", "").replace("gemini_", ""),
                                "response": {"result": block["content"]},
                            }
                        }]
                    })
                    continue  # Don't add to parts, added as separate message
            if parts:
                gemini_messages.append({"role": role, "parts": parts})

    print(f"      Gemini messages: {len(gemini_messages)}")
    for i, m in enumerate(gemini_messages):
        role = m.get("role", "?")
        parts_summary = [list(p.keys())[0] if isinstance(p, dict) else "?" for p in m.get("parts", [])]
        print(f"        [{i}] {role}: {parts_summary}")

    # Convert tools to Gemini function declarations
    function_declarations = []
    for tool in tools:
        function_declarations.append({
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        })

    print(f"      Tools: {len(function_declarations)}")

    response = client.models.generate_content(
        model=model_name,
        contents=gemini_messages,
        config=types.GenerateContentConfig(
            system_instruction=system,
            tools=[{"function_declarations": function_declarations}],
        ),
    )

    print(f"      ✓ Response received")

    # Check for function call
    if response.candidates and response.candidates[0].content.parts:
        part = response.candidates[0].content.parts[0]
        print(f"      Part type: {type(part).__name__}")

        if hasattr(part, 'function_call') and part.function_call:
            fc = part.function_call
            print(f"      → Function call: {fc.name}")
            return ChatResponse(
                content=[{
                    "type": "tool_use",
                    "id": f"gemini_{fc.name}",
                    "name": fc.name,
                    "input": dict(fc.args) if fc.args else {},
                }],
                stop_reason="tool_use",
            )
        elif hasattr(part, 'text') and part.text:
            print(f"      → Text response: {part.text[:100]}...")
            return ChatResponse(
                content=[{"type": "text", "text": part.text}],
                stop_reason="end_turn",
            )

    # Fallback
    text = response.text if hasattr(response, 'text') else str(response)
    print(f"      → Fallback text: {text[:100]}...")
    return ChatResponse(
        content=[{"type": "text", "text": text}],
        stop_reason="end_turn",
    )

async def _call_openai(api_key: str, messages: list, system: str, model_tier: str, tools: list) -> ChatResponse:
    """Call OpenAI API."""
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key)
    model = MODELS["openai"][model_tier]

    print(f"      Model: {model}")

    openai_messages = [{"role": "system", "content": system}]
    for msg in messages:
        if isinstance(msg["content"], str):
            openai_messages.append(msg)
        elif isinstance(msg["content"], list):
            # Handle tool results
            for block in msg["content"]:
                if block.get("type") == "tool_result":
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

    response = client.chat.completions.create(
        model=model,
        messages=openai_messages,
        tools=openai_tools if openai_tools else None,
    )
    
    print(f"      ✓ Response received")

    message = response.choices[0].message

    # Check for tool calls
    if message.tool_calls:
        tc = message.tool_calls[0]
        import json
        return ChatResponse(
            content=[{
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": json.loads(tc.function.arguments),
            }],
            stop_reason="tool_use",
        )

    return ChatResponse(
        content=[{"type": "text", "text": message.content}],
        stop_reason="end_turn",
        usage={
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        } if response.usage else None,
    )

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
    print(f"\n   Press Ctrl+C to stop\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")

if __name__ == "__main__":
    main()
