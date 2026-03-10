"""LLM provider abstraction layer."""

from .base import BaseLLMProvider, LLMResponse
from .claude import ClaudeProvider


def get_provider(
    provider: str = "claude",
    model: str = None,
    api_key: str = None,
) -> BaseLLMProvider:
    """
    Factory function to get an LLM provider.
    
    Args:
        provider: "claude", "openai", or "ollama"
        model: Model name (optional, uses defaults)
        api_key: API key (optional, uses env vars)
    
    Returns:
        LLM provider instance
    
    Examples:
        # Claude (default)
        provider = get_provider("claude", model="claude-haiku-4-5-20251001")
        
        # OpenAI
        provider = get_provider("openai", model="gpt-4o-mini")
        
        # Ollama (local)
        provider = get_provider("ollama", model="llama3.1:8b")
    """
    if provider == "claude":
        from .claude import ClaudeProvider
        return ClaudeProvider(
            model=model or "claude-haiku-4-5-20251001",
            api_key=api_key,
        )
    
    elif provider == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(
            model=model or "gpt-4o-mini",
            api_key=api_key,
        )
    
    elif provider == "ollama":
        from .ollama_provider import OllamaProvider
        return OllamaProvider(
            model=model or "llama3.1:8b",
        )
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'claude', 'openai', or 'ollama'.")


__all__ = ["get_provider", "BaseLLMProvider", "LLMResponse", "ClaudeProvider"]
