"""Claude (Anthropic) LLM provider with prompt caching."""

import os
from typing import Generator

import anthropic

from .base import BaseLLMProvider, LLMResponse


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude provider with prompt caching support."""
    
    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: str = None):
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
    
    def _prepare_cached_request(
        self,
        system_prompt: str | tuple[str, str],
        tools: list
    ) -> tuple[list, list]:
        """
        Prepare system prompt and tools with cache_control markers.

        Args:
            system_prompt: Either a single string (legacy) or a tuple of
                          (static_prompt, dynamic_context) for proper caching.
            tools: List of tool definitions.

        Caching strategy:
        - Static system prompt: cached (instructions + profile)
        - Tools: cached (definitions don't change)
        - Dynamic context: NOT cached (changes each call)
        """
        # Handle both legacy single-string and new split format
        if isinstance(system_prompt, tuple):
            static_prompt, dynamic_context = system_prompt
            cached_system = [
                {
                    "type": "text",
                    "text": static_prompt,
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "text",
                    "text": dynamic_context
                    # No cache_control — this changes each call
                }
            ]
        else:
            # Legacy: single string, cache the whole thing
            cached_system = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ]

        # Mark the last tool for caching (caches all tools)
        cached_tools = tools.copy()
        if cached_tools:
            cached_tools[-1] = {
                **cached_tools[-1],
                "cache_control": {"type": "ephemeral"}
            }

        return cached_system, cached_tools

    def chat(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat request to Claude with prompt caching."""
        cached_system, cached_tools = self._prepare_cached_request(system_prompt, tools)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=cached_system,
            tools=cached_tools,
            messages=messages,
        )
        
        # Log cache performance (useful for debugging/monitoring)
        if hasattr(response, 'usage'):
            usage = response.usage
            cache_read = getattr(usage, 'cache_read_input_tokens', 0)
            cache_create = getattr(usage, 'cache_creation_input_tokens', 0)
            if cache_read or cache_create:
                # Cache hit: cache_read > 0, Cache miss (first call): cache_create > 0
                pass  # Uncomment below to debug:
                print(f"  [Cache] read: {cache_read}, created: {cache_create}, input: {usage.input_tokens}")

        # Convert to standard format
        content = []
        for block in response.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        
        return LLMResponse(content=content, stop_reason=response.stop_reason)
    
    def chat_stream(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> Generator[dict, None, LLMResponse]:
        """Stream a chat response from Claude with prompt caching."""
        cached_system, cached_tools = self._prepare_cached_request(system_prompt, tools)

        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=cached_system,
            tools=cached_tools,
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "text":
                        pass  # Text will come in deltas
                    elif event.content_block.type == "tool_use":
                        yield {"type": "tool_start", "name": event.content_block.name, "id": event.content_block.id}
                
                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield {"type": "text", "content": event.delta.text}
                    elif event.delta.type == "input_json_delta":
                        yield {"type": "tool_input", "content": event.delta.partial_json}
            
            # Get final message
            final_message = stream.get_final_message()
            
            # Convert to standard format
            content = []
            for block in final_message.content:
                if block.type == "text":
                    content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
            
            return LLMResponse(content=content, stop_reason=final_message.stop_reason)
    
    def get_model_name(self) -> str:
        return self.model
