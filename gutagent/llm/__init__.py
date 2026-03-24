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
        provider: "claude", "openai", "ollama", "groq", or "gemini"
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

        # Groq (free tier available)
        provider = get_provider("groq", model="llama-3.1-70b-versatile")

        # Gemini (free tier available)
        provider = get_provider("gemini", model="gemini-1.5-flash")
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
    
    elif provider == "groq":
        from gutagent.llm.groq_provider import GroqProvider
        return GroqProvider(
            model=model or "llama-3.1-70b-versatile",
            api_key=api_key,
        )

    elif provider == "gemini":
        from gutagent.llm.gemini_provider import GeminiProvider
        return GeminiProvider(
            model=model or "gemini-1.5-flash",
            api_key=api_key,
        )

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'claude', 'openai', 'ollama', 'groq', or 'gemini'.")


__all__ = ["get_provider", "BaseLLMProvider", "LLMResponse"]
