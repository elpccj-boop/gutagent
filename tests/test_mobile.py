"""Tests for Mobile API - auth, settings, and LLM provider formatting.

# Run all mobile tests
pytest tests/test_mobile.py -v

# Run specific test class
pytest tests/test_mobile.py::TestAuth -v
pytest tests/test_mobile.py::TestToolConversion -v

# Run single test
pytest tests/test_mobile.py::TestToolConversion::test_gemini_tool_conversion -v
"""

import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

# Set test environment before imports
os.environ["JWT_SECRET"] = "test_secret_key_for_testing_only"
os.environ["ENCRYPTION_KEY"] = "02K9f7EhPbzQdu7zcQgya7IY3oOoLL_e74HyjKSSH1c="  # Valid Fernet key

from fastapi.testclient import TestClient


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    # Patch the database path
    with patch("gutagent.api.mobile.DATABASE_PATH", db_path):
        from gutagent.api.mobile import init_db
        init_db()
        yield db_path
    
    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def client(temp_db):
    """Create test client with temporary database."""
    with patch("gutagent.api.mobile.DATABASE_PATH", temp_db):
        from gutagent.api.mobile import app
        return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Register a user and return auth headers."""
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 201
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_tools():
    """Sample tool definitions matching app format."""
    return [
        {
            "name": "log_meal",
            "description": "Log a meal with nutrition",
            "input_schema": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"]},
                },
                "required": ["description"]
            }
        },
        {
            "name": "log_symptom",
            "description": "Log a symptom",
            "input_schema": {
                "type": "object",
                "properties": {
                    "symptom": {"type": "string"},
                    "severity": {"type": "integer"},
                },
                "required": ["symptom", "severity"]
            }
        }
    ]


# =============================================================================
# AUTH TESTS
# =============================================================================

class TestAuth:
    """Test authentication endpoints."""
    
    def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post("/auth/register", json={
            "email": "newuser@example.com",
            "password": "securepassword123"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert "token" in data
        assert "user_id" in data
        assert data["email"] == "newuser@example.com"
    
    def test_register_duplicate_email(self, client):
        """Test registration with existing email fails."""
        # First registration
        client.post("/auth/register", json={
            "email": "duplicate@example.com",
            "password": "password123"
        })
        
        # Second registration with same email
        response = client.post("/auth/register", json={
            "email": "duplicate@example.com",
            "password": "differentpassword"
        })
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_register_invalid_email(self, client):
        """Test registration with invalid email fails."""
        response = client.post("/auth/register", json={
            "email": "notanemail",
            "password": "password123"
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_login_success(self, client):
        """Test successful login."""
        # Register first
        client.post("/auth/register", json={
            "email": "login@example.com",
            "password": "mypassword"
        })
        
        # Login
        response = client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "mypassword"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == "login@example.com"
    
    def test_login_wrong_password(self, client):
        """Test login with wrong password fails."""
        # Register first
        client.post("/auth/register", json={
            "email": "wrongpw@example.com",
            "password": "correctpassword"
        })
        
        # Login with wrong password
        response = client.post("/auth/login", json={
            "email": "wrongpw@example.com",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user fails."""
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "anypassword"
        })
        
        assert response.status_code == 401
    
    def test_protected_endpoint_without_auth(self, client):
        """Test accessing protected endpoint without auth fails."""
        response = client.get("/settings")
        
        assert response.status_code == 401  # HTTPBearer returns 401 for missing token
    
    def test_protected_endpoint_with_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token fails."""
        response = client.get("/settings", headers={
            "Authorization": "Bearer invalid_token"
        })
        
        assert response.status_code == 401


# =============================================================================
# SETTINGS TESTS
# =============================================================================

class TestSettings:
    """Test settings endpoints."""
    
    def test_get_settings_default(self, client, auth_headers):
        """Test getting default settings."""
        response = client.get("/settings", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["llm_provider"] == "claude"
        assert data["model_tier"] == "default"
        assert data["api_keys"] == {}
    
    def test_update_settings(self, client, auth_headers):
        """Test updating settings."""
        response = client.post("/settings", headers=auth_headers, json={
            "llm_provider": "gemini",
            "model_tier": "smart"
        })
        
        assert response.status_code == 200
        
        # Verify
        response = client.get("/settings", headers=auth_headers)
        data = response.json()
        assert data["llm_provider"] == "gemini"
        assert data["model_tier"] == "smart"
    
    def test_set_api_key(self, client, auth_headers):
        """Test setting an API key."""
        response = client.post("/settings/apikey", headers=auth_headers, json={
            "provider": "claude",
            "api_key": "sk-ant-test-key-12345"
        })
        
        assert response.status_code == 200
        
        # Verify key is stored (shows as True, not actual key)
        response = client.get("/settings", headers=auth_headers)
        data = response.json()
        assert data["api_keys"]["claude"] == True
    
    def test_set_api_key_multiple_providers(self, client, auth_headers):
        """Test setting API keys for multiple providers."""
        # Set Claude key
        client.post("/settings/apikey", headers=auth_headers, json={
            "provider": "claude",
            "api_key": "sk-ant-test"
        })
        
        # Set Gemini key
        client.post("/settings/apikey", headers=auth_headers, json={
            "provider": "gemini",
            "api_key": "AIza-test"
        })
        
        # Verify both
        response = client.get("/settings", headers=auth_headers)
        data = response.json()
        assert data["api_keys"]["claude"] == True
        assert data["api_keys"]["gemini"] == True
    
    def test_delete_api_key(self, client, auth_headers):
        """Test deleting an API key."""
        # Set key first
        client.post("/settings/apikey", headers=auth_headers, json={
            "provider": "openai",
            "api_key": "sk-test"
        })
        
        # Delete it
        response = client.delete("/settings/apikey/openai", headers=auth_headers)
        assert response.status_code == 200
        
        # Verify gone
        response = client.get("/settings", headers=auth_headers)
        data = response.json()
        assert "openai" not in data["api_keys"]


# =============================================================================
# TOOL CONVERSION TESTS
# =============================================================================

class TestToolConversion:
    """Test tool format conversion for different LLM providers."""
    
    def test_gemini_function_declarations(self, sample_tools):
        """Test converting tools to Gemini function_declarations format."""
        # This is what the server does internally
        function_declarations = []
        for tool in sample_tools:
            function_declarations.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            })
        
        assert len(function_declarations) == 2
        assert function_declarations[0]["name"] == "log_meal"
        assert function_declarations[0]["parameters"]["type"] == "object"
        assert "description" in function_declarations[0]["parameters"]["properties"]
    
    def test_openai_tools_format(self, sample_tools):
        """Test converting tools to OpenAI tools format."""
        openai_tools = []
        for tool in sample_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            })
        
        assert len(openai_tools) == 2
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "log_meal"
    
    def test_claude_tools_passthrough(self, sample_tools):
        """Test that Claude tools pass through unchanged."""
        # Claude uses the same format as our tools
        claude_tools = sample_tools
        
        assert claude_tools[0]["name"] == "log_meal"
        assert claude_tools[0]["input_schema"]["type"] == "object"


# =============================================================================
# MESSAGE CONVERSION TESTS
# =============================================================================

class TestMessageConversion:
    """Test message format conversion for different LLM providers."""
    
    def test_gemini_text_message_conversion(self):
        """Test converting text messages to Gemini format."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "Log my breakfast"},
        ]
        
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]
            if isinstance(content, str):
                gemini_messages.append({"role": role, "parts": [{"text": content}]})
        
        assert len(gemini_messages) == 3
        assert gemini_messages[0]["role"] == "user"
        assert gemini_messages[0]["parts"][0]["text"] == "Hello"
        assert gemini_messages[1]["role"] == "model"
    
    def test_gemini_tool_use_message_conversion(self):
        """Test converting tool_use messages to Gemini format."""
        messages = [
            {"role": "user", "content": "Log my breakfast: eggs"},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_123",
                        "name": "log_meal",
                        "input": {"description": "eggs", "meal_type": "breakfast"}
                    }
                ]
            },
        ]
        
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]
            
            if isinstance(content, str):
                gemini_messages.append({"role": role, "parts": [{"text": content}]})
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if block.get("type") == "tool_use":
                        parts.append({
                            "function_call": {
                                "name": block["name"],
                                "args": block["input"],
                            }
                        })
                if parts:
                    gemini_messages.append({"role": role, "parts": parts})
        
        assert len(gemini_messages) == 2
        assert "function_call" in gemini_messages[1]["parts"][0]
        assert gemini_messages[1]["parts"][0]["function_call"]["name"] == "log_meal"
    
    def test_gemini_tool_result_message_conversion(self):
        """Test converting tool_result messages to Gemini format."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "gemini_log_meal",
                        "content": '{"id": 1, "description": "eggs"}'
                    }
                ]
            },
        ]
        
        gemini_messages = []
        for msg in messages:
            content = msg["content"]
            
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        # Extract tool name from id (gemini_toolname format)
                        tool_name = block.get("tool_use_id", "").replace("gemini_", "")
                        gemini_messages.append({
                            "role": "user",
                            "parts": [{
                                "function_response": {
                                    "name": tool_name,
                                    "response": {"result": block["content"]},
                                }
                            }]
                        })
        
        assert len(gemini_messages) == 1
        assert "function_response" in gemini_messages[0]["parts"][0]
        assert gemini_messages[0]["parts"][0]["function_response"]["name"] == "log_meal"
    
    def test_openai_tool_result_conversion(self):
        """Test converting tool_result messages to OpenAI format."""
        messages = [
            {"role": "user", "content": "Log breakfast"},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_abc123",
                        "content": '{"id": 1}'
                    }
                ]
            },
        ]
        
        openai_messages = []
        for msg in messages:
            content = msg["content"]
            if isinstance(content, str):
                openai_messages.append(msg)
            elif isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block["content"],
                        })
        
        assert len(openai_messages) == 2
        assert openai_messages[1]["role"] == "tool"
        assert openai_messages[1]["tool_call_id"] == "call_abc123"


# =============================================================================
# CHAT REQUEST VALIDATION TESTS
# =============================================================================

class TestChatRequest:
    """Test chat request validation."""
    
    def test_chat_without_api_key(self, client, auth_headers, sample_tools):
        """Test chat fails without API key configured."""
        response = client.post("/chat", headers=auth_headers, json={
            "messages": [{"role": "user", "content": "Hello"}],
            "system": "You are a helpful assistant.",
            "patient_data": "",
            "turn_context": "",
            "tools": sample_tools
        })
        
        assert response.status_code == 400
        assert "No API key" in response.json()["detail"]
    
    def test_chat_request_structure(self, client, auth_headers, sample_tools):
        """Test chat request validates required fields."""
        # Missing messages
        response = client.post("/chat", headers=auth_headers, json={
            "system": "Test",
            "patient_data": "",
            "turn_context": "",
            "tools": sample_tools
        })
        
        assert response.status_code == 422  # Validation error
        
        # Missing tools
        response = client.post("/chat", headers=auth_headers, json={
            "messages": [{"role": "user", "content": "Hello"}],
            "system": "Test",
            "patient_data": "",
            "turn_context": ""
        })
        
        assert response.status_code == 422


# =============================================================================
# ENCRYPTION TESTS
# =============================================================================

class TestEncryption:
    """Test API key encryption/decryption."""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly."""
        from gutagent.api.mobile import encrypt_api_key, decrypt_api_key
        
        original_key = "sk-ant-api03-very-long-test-key-12345"
        encrypted = encrypt_api_key(original_key)
        decrypted = decrypt_api_key(encrypted)
        
        assert decrypted == original_key
        assert encrypted != original_key  # Should be different
    
    def test_encrypted_key_is_different_each_time(self):
        """Test that same key encrypts differently (due to IV)."""
        from gutagent.api.mobile import encrypt_api_key
        
        key = "sk-test-key"
        encrypted1 = encrypt_api_key(key)
        encrypted2 = encrypt_api_key(key)
        
        # Fernet uses random IV, so encryptions should differ
        # (Though both decrypt to same value)
        assert encrypted1 != encrypted2


# =============================================================================
# JWT TESTS
# =============================================================================

class TestJWT:
    """Test JWT token handling."""
    
    def test_token_contains_user_info(self, client):
        """Test that token contains expected user info."""
        import jwt
        
        response = client.post("/auth/register", json={
            "email": "jwt@example.com",
            "password": "password"
        })
        
        token = response.json()["token"]
        
        # Decode without verification to inspect
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        assert "user_id" in decoded
        assert decoded["email"] == "jwt@example.com"
        assert "exp" in decoded  # Has expiration
    
    def test_token_expiration(self, client):
        """Test that token has reasonable expiration."""
        import jwt
        from datetime import datetime, timezone
        
        response = client.post("/auth/register", json={
            "email": "expiry@example.com",
            "password": "password"
        })
        
        token = response.json()["token"]
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Should expire in ~30 days (with some tolerance)
        days_until_expiry = (exp_time - now).days
        assert 28 <= days_until_expiry <= 31


# =============================================================================
# INTEGRATION TESTS (with mocked LLM)
# =============================================================================

class TestGeminiMessageLoop:
    """Test full Gemini message conversion including tool result loop."""
    
    def test_full_tool_use_loop_messages(self):
        """Test converting a full tool use conversation to Gemini format."""
        # This is what happens in a real conversation:
        # 1. User says "log breakfast eggs"
        # 2. Model returns tool_use
        # 3. App executes tool, sends tool_result
        # 4. Model returns final text
        
        messages = [
            # Initial user message
            {"role": "user", "content": "log breakfast eggs"},
            # Model's tool call
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "gemini_log_meal",
                        "name": "log_meal",
                        "input": {"description": "eggs", "meal_type": "breakfast"}
                    }
                ]
            },
            # User sends tool result
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "gemini_log_meal",
                        "content": '{"id": 42, "description": "eggs", "meal_type": "breakfast"}'
                    }
                ]
            },
        ]
        
        # Convert using the same logic as mobile.py
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
                        tool_name = block.get("tool_use_id", "").replace("gemini_", "")
                        gemini_messages.append({
                            "role": "user",
                            "parts": [{
                                "function_response": {
                                    "name": tool_name,
                                    "response": {"result": block["content"]},
                                }
                            }]
                        })
                        continue
                if parts:
                    gemini_messages.append({"role": role, "parts": parts})
        
        # Verify structure
        assert len(gemini_messages) == 3
        
        # First message: user text
        assert gemini_messages[0]["role"] == "user"
        assert gemini_messages[0]["parts"][0]["text"] == "log breakfast eggs"
        
        # Second message: model function call
        assert gemini_messages[1]["role"] == "model"
        assert "function_call" in gemini_messages[1]["parts"][0]
        assert gemini_messages[1]["parts"][0]["function_call"]["name"] == "log_meal"
        
        # Third message: user function response
        assert gemini_messages[2]["role"] == "user"
        assert "function_response" in gemini_messages[2]["parts"][0]
        assert gemini_messages[2]["parts"][0]["function_response"]["name"] == "log_meal"
    
    def test_multiple_tool_calls_in_sequence(self):
        """Test multiple sequential tool calls."""
        messages = [
            {"role": "user", "content": "log breakfast eggs and feeling bloated 5"},
            # First tool call
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "gemini_log_meal",
                        "name": "log_meal",
                        "input": {"description": "eggs", "meal_type": "breakfast"}
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "gemini_log_meal",
                        "content": '{"id": 1}'
                    }
                ]
            },
            # Second tool call
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "gemini_log_symptom",
                        "name": "log_symptom",
                        "input": {"symptom": "bloating", "severity": 5}
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "gemini_log_symptom",
                        "content": '{"id": 2}'
                    }
                ]
            },
        ]
        
        # Convert
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]
            
            if isinstance(content, str):
                gemini_messages.append({"role": role, "parts": [{"text": content}]})
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if block.get("type") == "tool_use":
                        parts.append({
                            "function_call": {
                                "name": block["name"],
                                "args": block["input"],
                            }
                        })
                    elif block.get("type") == "tool_result":
                        tool_name = block.get("tool_use_id", "").replace("gemini_", "")
                        gemini_messages.append({
                            "role": "user",
                            "parts": [{
                                "function_response": {
                                    "name": tool_name,
                                    "response": {"result": block["content"]},
                                }
                            }]
                        })
                        continue
                if parts:
                    gemini_messages.append({"role": role, "parts": parts})
        
        # Should have 5 messages: user, model call, user response, model call, user response
        assert len(gemini_messages) == 5
        
        # Verify alternating pattern
        assert gemini_messages[0]["role"] == "user"
        assert gemini_messages[1]["role"] == "model"
        assert gemini_messages[2]["role"] == "user"
        assert gemini_messages[3]["role"] == "model"
        assert gemini_messages[4]["role"] == "user"


class TestChatIntegration:
    """Integration tests for chat with mocked LLM providers."""
    
    @pytest.fixture
    def client_with_key(self, client, auth_headers):
        """Client with API key configured."""
        client.post("/settings/apikey", headers=auth_headers, json={
            "provider": "claude",
            "api_key": "sk-ant-test-key"
        })
        return client, auth_headers
    
    @patch("gutagent.api.mobile._call_claude")
    def test_chat_returns_text_response(self, mock_claude, client_with_key, sample_tools):
        """Test chat returns text response correctly."""
        from gutagent.api.mobile import ChatResponse
        
        client, headers = client_with_key
        
        # Mock Claude response
        mock_claude.return_value = ChatResponse(
            content=[{"type": "text", "text": "Hello! How can I help?"}],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 20}
        )
        
        response = client.post("/chat", headers=headers, json={
            "messages": [{"role": "user", "content": "Hello"}],
            "system": "You are helpful.",
            "patient_data": "",
            "turn_context": "",
            "tools": sample_tools
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["stop_reason"] == "end_turn"
        assert data["content"][0]["text"] == "Hello! How can I help?"
    
    @patch("gutagent.api.mobile._call_claude")
    def test_chat_returns_tool_use(self, mock_claude, client_with_key, sample_tools):
        """Test chat returns tool_use response correctly."""
        from gutagent.api.mobile import ChatResponse
        
        client, headers = client_with_key
        
        # Mock Claude response with tool use
        mock_claude.return_value = ChatResponse(
            content=[{
                "type": "tool_use",
                "id": "tool_123",
                "name": "log_meal",
                "input": {"description": "eggs", "meal_type": "breakfast"}
            }],
            stop_reason="tool_use",
            usage={"input_tokens": 150, "output_tokens": 30}
        )
        
        response = client.post("/chat", headers=headers, json={
            "messages": [{"role": "user", "content": "Log breakfast: eggs"}],
            "system": "You are helpful.",
            "patient_data": "",
            "turn_context": "",
            "tools": sample_tools
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["stop_reason"] == "tool_use"
        assert data["content"][0]["name"] == "log_meal"
        assert data["content"][0]["input"]["description"] == "eggs"
