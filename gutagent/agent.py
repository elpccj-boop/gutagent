"""Core agent loop — the heart of GutAgent."""

import json
from gutagent.tools.registry import execute_tool
from gutagent.prompts.system import build_static_system_prompt, build_dynamic_context
from gutagent.config import TOOLS, MAX_TOKENS, LLM_PROVIDER, get_model_for_tier
from gutagent.llm import get_provider

# Tools that create log entries — we track their results for edit context
LOG_TOOLS = {
    "log_meal": "meals",
    "log_symptom": "symptoms",
    "log_vital": "vitals",
    "log_medication_event": "medications",
    "log_sleep": "sleep",
    "log_exercise": "exercise",
    "log_journal": "journal",
}

# Tools that modify entries — update the context after
ALTER_TOOLS = {"correct_log"}


def format_recent_logs(recent_logs: dict) -> str:
    """Format recent_logs dict into a string for the prompt."""
    if not recent_logs:
        return ""

    lines = ["Recently logged (available for edits):"]
    for table, entries in recent_logs.items():
        for entry in entries:
            entry_id = entry.get("id", "?")
            # Try various field names to get a description
            desc = (
                entry.get("summary") or  # new compact meal format
                entry.get("description") or
                entry.get("symptom") or
                entry.get("vital_type") or
                entry.get("type") or  # vitals use "type"
                entry.get("reading") or  # vitals have "reading"
                entry.get("medication") or
                entry.get("event_type") or
                str(entry)[:50]
            )
            lines.append(f"  [{table}] id:{entry_id} — {desc}")

    return "\n".join(lines)


def run_agent(
    user_message: str,
    conversation_history: list,  # Kept for API compatibility, not used
    profile: dict,
    recent_logs: dict = None,  # Tracks recently logged entries per table
    last_exchange: dict = None,  # Last user Q + assistant response for context
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

    recent_logs tracks recently logged entries so user can say "change that"
    without specifying IDs. Format: {"meals": [entry1, entry2], "symptoms": [...]}

    last_exchange keeps minimal context for follow-ups like "yes" or "that's right".
    Format: {"user": "previous question", "assistant": "previous response"}
    """
    if recent_logs is None:
        recent_logs = {}
    if last_exchange is None:
        last_exchange = {}

    # Build system prompt as (static, dynamic) tuple for proper caching
    # Static part (instructions + profile) is cached, dynamic part (recent data) is not
    static_prompt = build_static_system_prompt(profile)
    dynamic_context = build_dynamic_context()

    # Add recent logs context if we have any
    logs_context = format_recent_logs(recent_logs)
    if logs_context:
        dynamic_context = dynamic_context + "\n\n" + logs_context

    system_prompt = (static_prompt, dynamic_context)

    if verbose:
        print(f"  [Static Context: {len(static_prompt)} chars]")
        print(f"  [Dynamic Context: {len(dynamic_context)} chars]")
        print(f"  [{len(TOOLS)} Tools: {len(str(TOOLS))} chars]")

    # Use passed model or default
    if model is None:
        model = get_model_for_tier("default")

    # Get LLM provider
    provider_name = provider or LLM_PROVIDER
    llm = get_provider(provider_name, model=model)

    # Messages for this turn - include last exchange for minimal context
    messages = []
    if last_exchange.get("user") and last_exchange.get("assistant"):
        messages.append({"role": "user", "content": last_exchange["user"]})
        messages.append({"role": "assistant", "content": last_exchange["assistant"]})
    messages.append({"role": "user", "content": user_message})

    # Track if any logs were created this turn
    logs_this_turn = {}

    # Agent loop — keeps going until LLM gives a text response
    max_iterations = 10  # Safety valve to prevent infinite loops
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        if verbose:
            print(f"\n  [Agent iteration {iteration}]")
            print(f"  [Messages: {len(messages)}]")
            '''for i, m in enumerate(messages):
                content = m["content"]
                if isinstance(content, str):
                    preview = content[:80] + "..." if len(content) > 80 else content
                    print(f"    {i+1}. {m['role']}: {preview}")
                else:
                    # Content is a list of blocks (tool_use, tool_result, etc.)
                    block_types = [b.get("type", "?") for b in content]
                    print(f"    {i+1}. {m['role']}: {block_types}")'''

        response = llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            tools=TOOLS,
            max_tokens=MAX_TOKENS,
        )
        
        if verbose:
            print(f"  [Stop reason: {response.stop_reason}]")
        
        if response.stop_reason == "tool_use":
            # Add assistant's tool request to messages
            messages.append({
                "role": "assistant",
                "content": response.content,
            })
            
            # Execute tools and collect results
            tool_results = []
            for block in response.get_tool_calls():
                tool_name = block['name']

                if verbose:
                    print(f"  🔧 {tool_name}({block['input']})")

                result = execute_tool(tool_name, block["input"])

                if verbose:
                    print(f"  → Result ({len(result)} chars):")
                    print(result)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result,
                })

                # Track log operations
                if tool_name in LOG_TOOLS:
                    table = LOG_TOOLS[tool_name]
                    try:
                        entry = json.loads(result)
                        if "id" in entry:
                            if table not in logs_this_turn:
                                logs_this_turn[table] = []
                            logs_this_turn[table].append(entry)
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Track alter operations
                elif tool_name in ALTER_TOOLS:
                    try:
                        entry = json.loads(result)
                        table = block["input"].get("table")
                        if table and "id" in entry:
                            # Update the entry in recent_logs
                            if table in recent_logs:
                                recent_logs[table] = [
                                    entry if e.get("id") == entry["id"] else e
                                    for e in recent_logs[table]
                                ]
                    except (json.JSONDecodeError, TypeError):
                        pass

            # Add tool results to messages
            messages.append({"role": "user", "content": tool_results})
            
        else:
            # Final response
            response_text = response.get_text()

            # Update recent_logs with entries from this turn
            # New logs replace old ones for the same table
            for table, entries in logs_this_turn.items():
                recent_logs[table] = entries

            # Create new last_exchange for next turn's context
            new_last_exchange = {
                "user": user_message,
                "assistant": response_text[:500]  # Truncate to avoid bloat
            }

            return response_text, recent_logs, new_last_exchange

    return "[Agent reached maximum iterations.]", recent_logs, {}
