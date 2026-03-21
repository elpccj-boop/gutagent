"""Base interface for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: list  # List of content blocks (text or tool_use)
    stop_reason: str  # "end_turn", "tool_use", etc.
    usage: dict = None  # Token usage info (optional)
    
    def get_text(self) -> str:
        """Extract text content from response."""
        parts = []
        for block in self.content:
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    
    def get_tool_calls(self) -> list:
        """Extract tool calls from response."""
        return [b for b in self.content if b.get("type") == "tool_use"]


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def chat(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat request and get a response."""
        pass
    
    @abstractmethod
    def chat_stream(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> Generator[dict, None, LLMResponse]:
        """
        Stream a chat response.
        
        Yields dicts with streaming events:
            {"type": "text", "content": "..."}
            {"type": "tool_start", "name": "..."}
            {"type": "tool_input", "content": "..."}
        
        Returns final LLMResponse when complete.
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model name/identifier."""
        pass
