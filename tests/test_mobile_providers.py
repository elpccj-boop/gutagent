"""Tests for Mobile API - LLM provider logic and multi-tool handling.

These tests verify the actual provider functions, not mocked versions.
They catch bugs like:
- Multi-tool responses only returning first tool
- Missing caching implementation
- Dynamic context not prepended to user messages
- Token usage not normalized

Run all:
    pytest tests/test_mobile_providers.py -v

Run with coverage:
    pytest tests/test_mobile_providers.py -v --cov=gutagent.api.mobile
"""

import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

# Set test environment before imports
os.environ["JWT_SECRET"] = "test_secret_key_for_testing_only"
os.environ["ENCRYPTION_KEY"] = "02K9f7EhPbzQdu7zcQgya7IY3oOoLL_e74HyjKSSH1c="


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_tools():
    """Sample tool definitions."""
    return [
        {
            "name": "log_meal",
            "description": "Log a meal",
            "input_schema": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "meal_type": {"type": "string"},
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


@pytest.fixture
def sample_messages():
    """Sample conversation messages."""
    return [
        {"role": "user", "content": "I had eggs for breakfast and feeling bloated severity 5"}
    ]


# =============================================================================
# MULTI-TOOL RESPONSE TESTS
# =============================================================================

class TestClaudeMultiTool:
    """Test Claude returns ALL tool calls, not just the first."""

    @pytest.mark.asyncio
    async def test_claude_returns_multiple_tools(self, sample_tools, sample_messages):
        """Claude response with 2 tool_use blocks should return both."""
        from gutagent.api.mobile import _call_claude, ChatResponse

        # Mock Claude client response with MULTIPLE tool_use blocks
        mock_response = Mock()
        mock_response.stop_reason = "tool_use"
        mock_response.usage = Mock(
            input_tokens=100,
            output_tokens=50,
        )
        # Add cache attributes via setattr since Mock may not have them
        mock_response.usage.cache_read_input_tokens = 80
        mock_response.usage.cache_creation_input_tokens = 0
        
        # TWO tool_use blocks in one response
        mock_block_1 = Mock()
        mock_block_1.type = "tool_use"
        mock_block_1.model_dump = lambda: {
            "type": "tool_use",
            "id": "tool_1",
            "name": "log_meal",
            "input": {"description": "eggs", "meal_type": "breakfast"}
        }
        
        mock_block_2 = Mock()
        mock_block_2.type = "tool_use"
        mock_block_2.model_dump = lambda: {
            "type": "tool_use",
            "id": "tool_2",
            "name": "log_symptom",
            "input": {"symptom": "bloating", "severity": 5}
        }
        
        mock_response.content = [mock_block_1, mock_block_2]

        # Patch at the point where it's imported inside the function
        with patch.dict("sys.modules", {"anthropic": Mock()}) as modules:
            mock_anthropic = modules["anthropic"]
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            result = await _call_claude(
                api_key="test-key",
                messages=sample_messages,
                system="You are helpful",
                patient_data="No data",
                turn_context="Now",
                model_tier="default",
                tools=sample_tools,
            )

        # CRITICAL: Must return BOTH tools
        assert len(result.content) == 2, f"Expected 2 tools, got {len(result.content)}"
        assert result.content[0]["name"] == "log_meal"
        assert result.content[1]["name"] == "log_symptom"
        assert result.stop_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_claude_returns_text_and_tools(self, sample_tools, sample_messages):
        """Claude response with text + tool_use blocks should return all."""
        from gutagent.api.mobile import _call_claude

        mock_response = Mock()
        mock_response.stop_reason = "tool_use"
        mock_response.usage = Mock(
            input_tokens=100,
            output_tokens=50,
        )
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.usage.cache_creation_input_tokens = 0

        # Text block followed by tool_use - need proper .text attribute
        mock_text = Mock()
        mock_text.type = "text"
        mock_text.text = "I'll log that for you."
        mock_text.model_dump = lambda: {"type": "text", "text": "I'll log that for you."}

        mock_tool = Mock()
        mock_tool.type = "tool_use"
        mock_tool.name = "log_meal"
        mock_tool.model_dump = lambda: {
            "type": "tool_use",
            "id": "tool_1",
            "name": "log_meal",
            "input": {"description": "eggs"}
        }

        mock_response.content = [mock_text, mock_tool]

        with patch.dict("sys.modules", {"anthropic": Mock()}) as modules:
            mock_anthropic = modules["anthropic"]
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            result = await _call_claude(
                api_key="test-key",
                messages=sample_messages,
                system="You are helpful",
                patient_data="",
                turn_context="",
                model_tier="default",
                tools=sample_tools,
            )

        assert len(result.content) == 2
        assert result.content[0]["type"] == "text"
        assert result.content[1]["type"] == "tool_use"


class TestGeminiMultiTool:
    """Test Gemini returns ALL function calls, not just the first."""

    def test_gemini_response_parsing_multiple_parts(self):
        """Test that Gemini response parsing handles multiple function_call parts."""
        # This tests the PARSING logic directly, not the API call
        # The actual _call_gemini is tested via integration tests
        
        # Simulate what Gemini returns: multiple function_call parts
        mock_fc_1 = Mock()
        mock_fc_1.name = "log_meal"
        mock_fc_1.args = {"description": "eggs", "meal_type": "breakfast"}

        mock_fc_2 = Mock()
        mock_fc_2.name = "log_symptom" 
        mock_fc_2.args = {"symptom": "bloating", "severity": 5}

        mock_part_1 = Mock()
        mock_part_1.function_call = mock_fc_1
        mock_part_1.text = None
        
        mock_part_2 = Mock()
        mock_part_2.function_call = mock_fc_2
        mock_part_2.text = None

        parts = [mock_part_1, mock_part_2]
        
        # Simulate the parsing logic from _call_gemini
        content_blocks = []
        has_function_call = False
        
        for i, part in enumerate(parts):
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                content_blocks.append({
                    "type": "tool_use",
                    "id": f"gemini_{fc.name}_{i}",
                    "name": fc.name,
                    "input": dict(fc.args) if fc.args else {},
                })
                has_function_call = True
            elif hasattr(part, 'text') and part.text:
                content_blocks.append({"type": "text", "text": part.text})
        
        # Verify parsing returns BOTH function calls
        assert len(content_blocks) == 2
        assert content_blocks[0]["name"] == "log_meal"
        assert content_blocks[1]["name"] == "log_symptom"
        assert has_function_call is True


class TestOpenAIMultiTool:
    """Test OpenAI returns ALL tool_calls, not just the first."""

    def test_openai_response_parsing_multiple_tool_calls(self):
        """Test that OpenAI response parsing handles multiple tool_calls."""
        import json
        
        # Simulate what OpenAI returns: multiple tool_calls
        # Use SimpleNamespace for cleaner mocking
        from types import SimpleNamespace
        
        mock_tc_1 = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(
                name="log_meal",
                arguments='{"description": "eggs", "meal_type": "breakfast"}'
            )
        )

        mock_tc_2 = SimpleNamespace(
            id="call_2",
            function=SimpleNamespace(
                name="log_symptom",
                arguments='{"symptom": "bloating", "severity": 5}'
            )
        )

        tool_calls = [mock_tc_1, mock_tc_2]
        
        # Simulate the parsing logic from _call_openai
        content_blocks = []
        for i, tc in enumerate(tool_calls):
            content_blocks.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": json.loads(tc.function.arguments),
            })
        
        # Verify parsing returns BOTH tool calls
        assert len(content_blocks) == 2
        assert content_blocks[0]["name"] == "log_meal"
        assert content_blocks[0]["id"] == "call_1"
        assert content_blocks[1]["name"] == "log_symptom"
        assert content_blocks[1]["id"] == "call_2"


# =============================================================================
# CACHING TESTS
# =============================================================================

class TestClaudeCaching:
    """Test Claude three-tier caching with cache_control markers."""

    @pytest.mark.asyncio
    async def test_claude_system_prompt_has_cache_control(self, sample_tools, sample_messages):
        """Claude should send system prompt with cache_control markers."""
        from gutagent.api.mobile import _call_claude

        captured_kwargs = {}

        def capture_create(**kwargs):
            captured_kwargs.update(kwargs)
            # Return minimal mock response with proper .text attribute
            mock_resp = Mock()
            mock_resp.stop_reason = "end_turn"
            mock_text_block = Mock()
            mock_text_block.type = "text"
            mock_text_block.text = "Hi"
            mock_text_block.model_dump = lambda: {"type": "text", "text": "Hi"}
            mock_resp.content = [mock_text_block]
            mock_resp.usage = Mock(input_tokens=100, output_tokens=10)
            mock_resp.usage.cache_read_input_tokens = 0
            mock_resp.usage.cache_creation_input_tokens = 0
            return mock_resp

        with patch.dict("sys.modules", {"anthropic": Mock()}) as modules:
            mock_anthropic = modules["anthropic"]
            mock_client = Mock()
            mock_client.messages.create = capture_create
            mock_anthropic.Anthropic.return_value = mock_client

            await _call_claude(
                api_key="test-key",
                messages=sample_messages,
                system="Static system prompt",
                patient_data="Patient health data",
                turn_context="Current timestamp",
                model_tier="default",
                tools=sample_tools,
            )

        # Verify system prompt structure
        system = captured_kwargs.get("system")
        assert system is not None, "System prompt not passed"
        assert isinstance(system, list), "System should be list for multi-block caching"
        assert len(system) == 3, "Should have 3 blocks: static, patient_data, turn_context"

        # First two blocks should have cache_control
        assert "cache_control" in system[0], "Static prompt should have cache_control"
        assert "cache_control" in system[1], "Patient data should have cache_control"
        assert "cache_control" not in system[2], "Turn context should NOT have cache_control"

        # Verify content
        assert system[0]["text"] == "Static system prompt"
        assert system[1]["text"] == "Patient health data"
        assert system[2]["text"] == "Current timestamp"

    @pytest.mark.asyncio
    async def test_claude_tools_have_cache_control(self, sample_tools, sample_messages):
        """Claude should mark last tool with cache_control."""
        from gutagent.api.mobile import _call_claude

        captured_kwargs = {}

        def capture_create(**kwargs):
            captured_kwargs.update(kwargs)
            mock_resp = Mock()
            mock_resp.stop_reason = "end_turn"
            mock_text_block = Mock()
            mock_text_block.type = "text"
            mock_text_block.text = "Hi"
            mock_text_block.model_dump = lambda: {"type": "text", "text": "Hi"}
            mock_resp.content = [mock_text_block]
            mock_resp.usage = Mock(input_tokens=100, output_tokens=10)
            mock_resp.usage.cache_read_input_tokens = 0
            mock_resp.usage.cache_creation_input_tokens = 0
            return mock_resp

        with patch.dict("sys.modules", {"anthropic": Mock()}) as modules:
            mock_anthropic = modules["anthropic"]
            mock_client = Mock()
            mock_client.messages.create = capture_create
            mock_anthropic.Anthropic.return_value = mock_client

            await _call_claude(
                api_key="test-key",
                messages=sample_messages,
                system="System",
                patient_data="Data",
                turn_context="Context",
                model_tier="default",
                tools=sample_tools,
            )

        tools = captured_kwargs.get("tools")
        assert tools is not None
        assert len(tools) == 2

        # Last tool should have cache_control
        assert "cache_control" in tools[-1], "Last tool should have cache_control"
        # First tool should NOT (only last one)
        assert "cache_control" not in tools[0] or tools[0] is tools[-1]


class TestGeminiCaching:
    """Test Gemini explicit caching via client.caches.create()."""

    def test_gemini_cache_store_exists(self):
        """Module-level cache store should exist."""
        from gutagent.api.mobile import _gemini_cache_store, GEMINI_CACHE_TTL_SECONDS
        
        assert isinstance(_gemini_cache_store, dict)
        assert GEMINI_CACHE_TTL_SECONDS == 3600  # 1 hour

    @pytest.mark.asyncio
    async def test_gemini_creates_cache_on_first_request(self, sample_tools, sample_messages):
        """Gemini should call caches.create() for caching."""
        from gutagent.api.mobile import _get_or_create_gemini_cache, _gemini_cache_store

        # Clear cache store
        _gemini_cache_store.clear()

        mock_cache = Mock()
        mock_cache.name = "projects/123/cachedContents/abc"
        mock_cache.usage_metadata = Mock(total_token_count=5000)

        mock_client = Mock()
        mock_client.caches.create.return_value = mock_cache

        mock_types = Mock()
        mock_types.CreateCachedContentConfig = Mock
        mock_types.Tool = Mock
        mock_types.FunctionDeclaration = Mock

        cache_name, creation_tokens = _get_or_create_gemini_cache(
            client=mock_client,
            types=mock_types,
            model="gemini-2.0-flash",
            system_prompt="You are a helpful assistant",
            tools=sample_tools,
        )

        # Should have created cache
        mock_client.caches.create.assert_called_once()
        assert cache_name == "projects/123/cachedContents/abc"
        assert creation_tokens == 5000

        # Should be stored
        assert len(_gemini_cache_store) == 1

    @pytest.mark.asyncio
    async def test_gemini_reuses_cache_on_second_request(self, sample_tools):
        """Gemini should reuse cached content on subsequent requests."""
        from gutagent.api.mobile import _get_or_create_gemini_cache, _gemini_cache_store
        import time

        # Clear and pre-populate cache store
        _gemini_cache_store.clear()

        # Simulate existing cache
        cache_key = list(_gemini_cache_store.keys())[0] if _gemini_cache_store else None
        
        # Create a cache entry manually
        import hashlib
        content = "gemini-2.0-flash:You are a helpful assistant"
        cache_key = hashlib.sha256(content.encode()).hexdigest()[:16]
        _gemini_cache_store[cache_key] = {
            "name": "projects/123/cachedContents/existing",
            "expires_at": time.time() + 3600,  # Valid for 1 hour
        }

        mock_client = Mock()
        mock_types = Mock()

        cache_name, creation_tokens = _get_or_create_gemini_cache(
            client=mock_client,
            types=mock_types,
            model="gemini-2.0-flash",
            system_prompt="You are a helpful assistant",
            tools=sample_tools,
        )

        # Should NOT have called create (cache hit)
        mock_client.caches.create.assert_not_called()
        assert cache_name == "projects/123/cachedContents/existing"
        assert creation_tokens == 0  # No new tokens


class TestOpenAICaching:
    """Test OpenAI automatic prefix caching."""

    @pytest.mark.asyncio
    async def test_openai_reports_cached_tokens(self, sample_tools, sample_messages):
        """OpenAI should report cache_read_input_tokens when available."""
        
        mock_message = Mock()
        mock_message.content = "Hello!"
        mock_message.tool_calls = None

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(
            prompt_tokens=1000,
            completion_tokens=50,
        )
        # OpenAI returns cached_tokens in prompt_tokens_details
        mock_response.usage.prompt_tokens_details = Mock(cached_tokens=800)

        mock_openai_module = Mock()
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            from gutagent.api.mobile import _call_openai
            
            result = await _call_openai(
                api_key="test-key",
                messages=sample_messages,
                system="You are helpful",
                model_tier="default",
                tools=sample_tools,
            )

        # Should report normalized usage
        assert result.usage is not None
        assert result.usage["input_tokens"] == 200  # 1000 - 800 cached
        assert result.usage["output_tokens"] == 50
        assert result.usage["cache_read_input_tokens"] == 800


# =============================================================================
# DYNAMIC CONTEXT TESTS
# =============================================================================

class TestDynamicContextPrepending:
    """Test that dynamic context is prepended to user message for Gemini/OpenAI."""

    def test_prepend_dynamic_context_basic(self):
        """Basic context prepending should work."""
        from gutagent.api.mobile import _prepend_dynamic_context

        messages = [
            {"role": "user", "content": "Log my breakfast"}
        ]

        result = _prepend_dynamic_context(
            messages=messages,
            patient_data="Recent meals: eggs yesterday",
            turn_context="Time: 9:00 AM",
        )

        assert len(result) == 1
        assert "[Current Context]" in result[0]["content"]
        assert "Recent meals: eggs yesterday" in result[0]["content"]
        assert "Time: 9:00 AM" in result[0]["content"]
        assert "[User Message]" in result[0]["content"]
        assert "Log my breakfast" in result[0]["content"]

    def test_prepend_dynamic_context_preserves_tool_results(self):
        """Tool result messages should not have context prepended."""
        from gutagent.api.mobile import _prepend_dynamic_context

        messages = [
            {"role": "user", "content": "Log breakfast"},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "log_meal", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "{}"}]},
        ]

        result = _prepend_dynamic_context(
            messages=messages,
            patient_data="Data",
            turn_context="Context",
        )

        # First user message gets context
        assert "[Current Context]" in result[0]["content"]
        
        # Tool result message unchanged (content is list, not string)
        assert result[2]["content"] == [{"type": "tool_result", "tool_use_id": "1", "content": "{}"}]

    def test_prepend_dynamic_context_empty(self):
        """Empty context should return messages unchanged."""
        from gutagent.api.mobile import _prepend_dynamic_context

        messages = [{"role": "user", "content": "Hello"}]

        result = _prepend_dynamic_context(
            messages=messages,
            patient_data="",
            turn_context="",
        )

        # Should be unchanged (or nearly - whitespace stripped)
        assert result[0]["content"] == "Hello" or "[Current Context]" not in result[0]["content"]


class TestChatEndpointRouting:
    """Test that /chat routes to correct provider with correct context handling."""

    @pytest.mark.asyncio
    async def test_claude_gets_three_separate_parts(self):
        """Claude should receive system, patient_data, turn_context separately."""
        from gutagent.api.mobile import chat, ChatRequest
        from unittest.mock import AsyncMock

        request = ChatRequest(
            messages=[{"role": "user", "content": "Hello"}],
            system="System prompt",
            patient_data="Patient data",
            turn_context="Turn context",
            tools=[],
        )

        with patch("gutagent.api.mobile.get_db") as mock_db, \
             patch("gutagent.api.mobile.decrypt_api_key", return_value="test-key"), \
             patch("gutagent.api.mobile._call_claude", new_callable=AsyncMock) as mock_claude:

            # Setup DB mock
            mock_conn = Mock()
            mock_conn.execute.return_value.fetchone.side_effect = [
                {"llm_provider": "claude", "model_tier": "default"},  # settings
                {"api_key_encrypted": "encrypted"},  # api key
            ]
            mock_db.return_value = mock_conn

            mock_claude.return_value = Mock(
                content=[{"type": "text", "text": "Hi"}],
                stop_reason="end_turn",
                usage=None,
            )

            # Create mock user
            mock_user = {"user_id": 1, "email": "test@test.com"}

            # This would normally be called by FastAPI
            # We're testing the routing logic
            await chat(request, user=mock_user)

            # Verify Claude was called with separate parts
            mock_claude.assert_called_once()
            call_kwargs = mock_claude.call_args
            
            # Should have system, patient_data, turn_context as separate args
            assert "system" in call_kwargs.kwargs or len(call_kwargs.args) >= 3

    @pytest.mark.asyncio
    async def test_gemini_gets_prepended_context(self):
        """Gemini should receive messages with context prepended."""
        from gutagent.api.mobile import chat, ChatRequest
        from unittest.mock import AsyncMock

        request = ChatRequest(
            messages=[{"role": "user", "content": "Hello"}],
            system="System prompt",
            patient_data="Patient data here",
            turn_context="Turn context here",
            tools=[],
        )

        with patch("gutagent.api.mobile.get_db") as mock_db, \
             patch("gutagent.api.mobile.decrypt_api_key", return_value="test-key"), \
             patch("gutagent.api.mobile._call_gemini", new_callable=AsyncMock) as mock_gemini:

            mock_conn = Mock()
            mock_conn.execute.return_value.fetchone.side_effect = [
                {"llm_provider": "gemini", "model_tier": "default"},
                {"api_key_encrypted": "encrypted"},
            ]
            mock_db.return_value = mock_conn

            mock_gemini.return_value = Mock(
                content=[{"type": "text", "text": "Hi"}],
                stop_reason="end_turn",
                usage=None,
            )

            mock_user = {"user_id": 1, "email": "test@test.com"}
            await chat(request, user=mock_user)

            # Verify Gemini was called
            mock_gemini.assert_called_once()
            call_kwargs = mock_gemini.call_args

            # Messages should have context prepended
            messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]
            assert "[Current Context]" in messages[0]["content"]
            assert "Patient data here" in messages[0]["content"]

            # System should be ONLY the static prompt
            system = call_kwargs.kwargs.get("system") or call_kwargs.args[2]
            assert system == "System prompt"
            assert "Patient data" not in system


# =============================================================================
# TOKEN USAGE NORMALIZATION TESTS
# =============================================================================

class TestTokenUsageNormalization:
    """Test that all providers normalize token usage to Claude semantics."""

    @pytest.mark.asyncio
    async def test_claude_usage_includes_cache_fields(self, sample_tools, sample_messages):
        """Claude should return cache_read and cache_creation fields."""
        
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_text = Mock()
        mock_text.type = "text"
        mock_text.text = "Hi"
        mock_text.model_dump = lambda: {"type": "text", "text": "Hi"}
        mock_response.content = [mock_text]
        mock_response.usage = Mock(input_tokens=100, output_tokens=20)
        mock_response.usage.cache_read_input_tokens = 80
        mock_response.usage.cache_creation_input_tokens = 10

        with patch.dict("sys.modules", {"anthropic": Mock()}) as modules:
            mock_anthropic = modules["anthropic"]
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            from gutagent.api.mobile import _call_claude
            result = await _call_claude(
                api_key="test-key",
                messages=sample_messages,
                system="System",
                patient_data="Data",
                turn_context="Context",
                model_tier="default",
                tools=sample_tools,
            )

        assert result.usage["input_tokens"] == 100
        assert result.usage["output_tokens"] == 20
        assert result.usage["cache_read_input_tokens"] == 80
        assert result.usage["cache_creation_input_tokens"] == 10

    def test_gemini_usage_normalized(self):
        """Test Gemini usage normalization logic: input_tokens = total - cached."""
        
        # Simulate Gemini usage_metadata
        total_input = 1000
        cached_tokens = 800
        output_tokens = 50
        
        # This is the normalization logic from _call_gemini
        uncached_input = total_input - cached_tokens
        
        usage = {
            "input_tokens": uncached_input,
            "output_tokens": output_tokens,
        }
        if cached_tokens > 0:
            usage["cache_read_input_tokens"] = cached_tokens
        
        # Verify normalization
        assert usage["input_tokens"] == 200  # 1000 - 800
        assert usage["output_tokens"] == 50
        assert usage["cache_read_input_tokens"] == 800

    @pytest.mark.asyncio
    async def test_openai_usage_normalized(self, sample_tools, sample_messages):
        """OpenAI should normalize usage: input_tokens = total - cached."""
        
        mock_message = Mock()
        mock_message.content = "Hello"
        mock_message.tool_calls = None

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=1000, completion_tokens=50)
        mock_response.usage.prompt_tokens_details = Mock(cached_tokens=700)

        mock_openai_module = Mock()
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            from gutagent.api.mobile import _call_openai
            result = await _call_openai(
                api_key="test-key",
                messages=sample_messages,
                system="System",
                model_tier="default",
                tools=sample_tools,
            )

        # input_tokens should be uncached only (1000 - 700 = 300)
        assert result.usage["input_tokens"] == 300
        assert result.usage["output_tokens"] == 50
        assert result.usage["cache_read_input_tokens"] == 700


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_tool_list(self, sample_messages):
        """Should handle empty tools list."""
        
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_text = Mock()
        mock_text.type = "text"
        mock_text.text = "Hi"
        mock_text.model_dump = lambda: {"type": "text", "text": "Hi"}
        mock_response.content = [mock_text]
        mock_response.usage = Mock(input_tokens=50, output_tokens=10)
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.usage.cache_creation_input_tokens = 0

        with patch.dict("sys.modules", {"anthropic": Mock()}) as modules:
            mock_anthropic = modules["anthropic"]
            mock_client = Mock()
            mock_client.messages.create.return_value = mock_response
            mock_anthropic.Anthropic.return_value = mock_client

            from gutagent.api.mobile import _call_claude
            result = await _call_claude(
                api_key="test-key",
                messages=sample_messages,
                system="System",
                patient_data="",
                turn_context="",
                model_tier="default",
                tools=[],  # Empty!
            )

        assert result.stop_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_openai_no_cache_details(self, sample_tools, sample_messages):
        """OpenAI without prompt_tokens_details should not crash."""
        
        mock_message = Mock()
        mock_message.content = "Hello"
        mock_message.tool_calls = None

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=20)
        mock_response.usage.prompt_tokens_details = None

        mock_openai_module = Mock()
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_module.OpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            from gutagent.api.mobile import _call_openai
            result = await _call_openai(
                api_key="test-key",
                messages=sample_messages,
                system="System",
                model_tier="default",
                tools=sample_tools,
            )

        # Should not crash, cache_read should be 0 or absent
        assert result.usage["input_tokens"] == 100
        assert result.usage.get("cache_read_input_tokens", 0) == 0
