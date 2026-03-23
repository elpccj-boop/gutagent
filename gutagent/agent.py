"""Core agent loop — the heart of GutAgent (CLI version)."""

from gutagent.core import (
    build_messages,
    build_system_prompt,
    execute_tool_calls,
    finalize_turn,
    MAX_ITERATIONS,
)
from gutagent.config import TOOLS, MAX_TOKENS, LLM_PROVIDER, get_model_for_tier
from gutagent.llm import get_provider


def run_agent(
    user_message: str,
    profile: dict,
    recent_logs: dict = None,
    last_exchange: dict = None,
    verbose: bool = False,
    model: str = None,
    provider: str = None,
) -> tuple[str, dict, dict]:
    """
    Core agent loop:
    
    1. Send user message + tools to LLM
    2. If LLM wants to use a tool → execute it → feed result back
    3. Repeat until LLM produces a final text response
    4. Return (response_text, updated_recent_logs, new_last_exchange)

    Args:
        user_message: The user's input.
        profile: User's medical profile dict.
        recent_logs: Tracks recently logged entries per table for "change that" edits.
        last_exchange: Last user Q + assistant response for follow-up context.
        verbose: If True, print tool calls and token usage.
        model: Model name override (default uses get_model_for_tier).
        provider: Provider name override (default uses LLM_PROVIDER env var).

    Returns:
        Tuple of (response_text, updated_recent_logs, new_last_exchange).
    """
    if recent_logs is None:
        recent_logs = {}
    if last_exchange is None:
        last_exchange = {}

    # Build system prompt as (static, dynamic) tuple for proper caching
    system_prompt = build_system_prompt(profile, recent_logs)

    # Use passed model or default
    if model is None:
        model = get_model_for_tier("default")

    # Get LLM provider
    provider_name = provider or LLM_PROVIDER
    llm = get_provider(provider_name, model=model)

    # Build messages with last exchange context
    messages = build_messages(user_message, last_exchange)

    # Track logs created this turn
    logs_this_turn = {}

    # Track cumulative token usage
    cumulative_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }

    # Agent loop — keeps going until LLM gives a text response
    iteration = 0
    
    while iteration < MAX_ITERATIONS:
        iteration += 1
        
        if verbose:
            print(f"\n  [Agent iteration {iteration}]")
            print(f"  [Messages: {len(messages)}]")

        response = llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            tools=TOOLS,
            max_tokens=MAX_TOKENS,
        )
        
        # Track token usage
        if response.usage:
            usage = response.usage
            cumulative_usage["input_tokens"] += usage.get("input_tokens", 0)
            cumulative_usage["output_tokens"] += usage.get("output_tokens", 0)
            cumulative_usage["cache_creation_input_tokens"] += usage.get("cache_creation_input_tokens", 0)
            cumulative_usage["cache_read_input_tokens"] += usage.get("cache_read_input_tokens", 0)

            if verbose:
                in_tok = usage.get("input_tokens", 0)
                out_tok = usage.get("output_tokens", 0)
                cache_read = usage.get("cache_read_input_tokens", 0)
                cache_create = usage.get("cache_creation_input_tokens", 0)

                print(f"  [Tokens] in={in_tok} out={out_tok}", end="")
                if cache_read > 0:
                    print(f" cache_read={cache_read}", end="")
                if cache_create > 0:
                    print(f" cache_create={cache_create}", end="")
                print()

        if verbose:
            print(f"  [Stop reason: {response.stop_reason}]")
        
        if response.stop_reason == "tool_use":
            # Add assistant's tool request to messages
            messages.append({
                "role": "assistant",
                "content": response.content,
            })
            
            # Execute tools using shared logic
            tool_results = execute_tool_calls(
                tool_calls=response.get_tool_calls(),
                recent_logs=recent_logs,
                logs_this_turn=logs_this_turn,
                verbose=verbose,
            )

            # Add tool results to messages
            messages.append({"role": "user", "content": tool_results})
            
        else:
            # Final response
            response_text = response.get_text()

            # Print cumulative token usage summary
            if verbose:
                _print_usage_summary(cumulative_usage)

            # Finalize turn using shared logic
            new_last_exchange = finalize_turn(
                user_message=user_message,
                response_text=response_text,
                recent_logs=recent_logs,
                logs_this_turn=logs_this_turn,
            )

            return response_text, recent_logs, new_last_exchange

    return "[Agent reached maximum iterations.]", recent_logs, {}


def _print_usage_summary(cumulative_usage: dict) -> None:
    """Print token usage summary for verbose mode."""
    total_in = cumulative_usage["input_tokens"]
    total_out = cumulative_usage["output_tokens"]
    cache_create = cumulative_usage["cache_creation_input_tokens"]
    cache_read = cumulative_usage["cache_read_input_tokens"]
    total_all = total_in + total_out + cache_create + cache_read

    print(f"\n  {'=' * 50}")
    print(f"  [Token Usage Summary]")
    print(f"  {'=' * 50}")
    print(f"  Input tokens:        {total_in:>8}")
    print(f"  Output tokens:       {total_out:>8}")

    if cache_create > 0 or cache_read > 0:
        print(f"  {'-' * 50}")
        if cache_create > 0:
            print(f"  Cache write:         {cache_create:>8}")
        if cache_read > 0:
            print(f"  Cache read:          {cache_read:>8}")

    print(f"  {'-' * 50}")
    print(f"  Total tokens:        {total_all:>8}")
    print(f"  {'=' * 50}")
