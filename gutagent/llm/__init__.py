"""LLM provider abstraction layer."""

from .base import BaseLLMProvider, LLMResponse


def get_provider(
    provider: str = "claude",
    model: str = None,
    api_key: str = None,
) -> BaseLLMProvider:
    """
    Factory function to get an LLM provider.
    
    Args:
        provider: "claude", "gemini", or "openai"
        model: Model name (optional, uses defaults)
        api_key: API key (optional, uses env vars)

    Returns:
        LLM provider instance
    
    Environment variables:
        ANTHROPIC_API_KEY: Claude API key
        GEMINI_API_KEY: Gemini API key
        OPENAI_API_KEY: OpenAI API key
        CLAUDE_CACHE_TTL: Cache TTL for Claude (None=5min, "1h"=1 hour)

    Examples:
        provider = get_provider("claude", model="claude-haiku-4-5-20251001")
        provider = get_provider("gemini", model="gemini-2.5-flash")
        provider = get_provider("openai", model="gpt-4o-mini")
    """
    if provider == "claude":
        from .claude_provider import ClaudeProvider
        return ClaudeProvider(
            model=model or "claude-haiku-4-5-20251001",
            api_key=api_key,
        )

    elif provider == "gemini":
        from gutagent.llm.gemini_provider import GeminiProvider
        return GeminiProvider(
            model=model or "gemini-2.5-flash",
            api_key=api_key,
        )
    
    elif provider == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(
            model=model or "gpt-4o-mini",
            api_key=api_key,
        )

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'claude', 'gemini' or 'openai'.")


__all__ = ["get_provider", "BaseLLMProvider", "LLMResponse"]
