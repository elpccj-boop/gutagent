"""Shared core logic for GutAgent — used by both CLI and web interfaces."""

import json
from gutagent.prompts.system import build_static_system_prompt, build_dynamic_context
from gutagent.tools.registry import execute_tool


# Tools that create log entries — we track their results for edit context
LOG_TOOLS = {
    "log_meal": "meals",
    "log_symptom": "symptoms",
    "log_vital": "vitals",
    "log_lab": "labs",
    "log_medication_event": "medications",
    "log_sleep": "sleep",
    "log_exercise": "exercise",
    "log_journal": "journal",
}

# Tools that modify entries
ALTER_TOOLS = {"correct_log"}

# Maximum agent loop iterations (safety valve)
MAX_ITERATIONS = 10


def format_recent_logs(recent_logs: dict) -> str:
    """Format recent_logs dict into a string for the system prompt.
    
    Args:
        recent_logs: Dict mapping table names to lists of entry dicts.
                    e.g. {"meals": [{"id": 1, "description": "eggs"}]}
    
    Returns:
        Formatted string for inclusion in system prompt, or empty string if no logs.
    """
    if not recent_logs:
        return ""

    lines = ["Recently logged (available for edits):"]
    for table, entries in recent_logs.items():
        for entry in entries:
            entry_id = entry.get("id", "?")
            # Try various field names to get a description
            desc = (
                entry.get("summary") or
                entry.get("description") or
                entry.get("symptom") or
                entry.get("vital_type") or
                entry.get("type") or
                entry.get("reading") or
                entry.get("test_name") or
                entry.get("medication") or
                entry.get("event_type") or
                str(entry)[:50]
            )
            lines.append(f"  [{table}] id:{entry_id} — {desc}")

    return "\n".join(lines)


def build_messages(user_message: str, last_exchange: dict) -> list:
    """Build messages list with optional last exchange context.
    
    Args:
        user_message: The current user message.
        last_exchange: Dict with "user" and "assistant" keys from previous turn.
    
    Returns:
        List of message dicts ready for LLM API.
    """
    messages = []
    if last_exchange.get("user") and last_exchange.get("assistant"):
        messages.append({"role": "user", "content": last_exchange["user"]})
        messages.append({"role": "assistant", "content": last_exchange["assistant"]})
    messages.append({"role": "user", "content": user_message})
    return messages


def build_system_prompt(profile: dict, recent_logs: dict) -> tuple[str, str]:
    """Build system prompt as (static, dynamic) tuple.
    
    Args:
        profile: User's medical profile dict.
        recent_logs: Recently logged entries for edit context.
    
    Returns:
        Tuple of (static_prompt, dynamic_context) strings.
        Static part can be cached, dynamic part changes each call.
    """
    static = build_static_system_prompt(profile)
    dynamic = build_dynamic_context()
    
    logs_context = format_recent_logs(recent_logs)
    if logs_context:
        dynamic = dynamic + "\n\n" + logs_context
    
    return (static, dynamic)


def track_log_operation(
    tool_name: str,
    tool_input: dict,
    result: str,
    recent_logs: dict,
    logs_this_turn: dict,
) -> None:
    """Track log and alter operations for edit context.
    
    Modifies logs_this_turn (for new entries) and recent_logs (for updates) in place.
    
    Args:
        tool_name: Name of the tool that was executed.
        tool_input: Input dict passed to the tool.
        result: JSON string result from the tool.
        recent_logs: Session's recent_logs dict (modified in place for ALTER_TOOLS).
        logs_this_turn: Dict tracking new logs this turn (modified in place for LOG_TOOLS).
    """
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
    
    elif tool_name in ALTER_TOOLS:
        try:
            entry = json.loads(result)
            table = tool_input.get("table")
            if table and "id" in entry:
                # Update the entry in recent_logs
                if table in recent_logs:
                    recent_logs[table] = [
                        entry if e.get("id") == entry["id"] else e
                        for e in recent_logs[table]
                    ]
        except (json.JSONDecodeError, TypeError):
            pass


def execute_tool_calls(
    tool_calls: list,
    recent_logs: dict,
    logs_this_turn: dict,
    verbose: bool = False,
    show_tools_callback=None,
) -> list:
    """Execute a list of tool calls and return results.
    
    Args:
        tool_calls: List of tool call dicts with 'id', 'name', 'input' keys.
        recent_logs: Session's recent_logs (modified for ALTER_TOOLS).
        logs_this_turn: Tracks new logs this turn (modified for LOG_TOOLS).
        verbose: If True, print tool execution details (CLI mode).
        show_tools_callback: Optional callback(tool_name, input, result) for web streaming.
    
    Returns:
        List of tool_result dicts ready to append to messages.
    """
    tool_results = []
    
    for block in tool_calls:
        tool_name = block['name']
        tool_input = block['input']
        
        if verbose:
            print(f"  🔧 {tool_name}({json.dumps(tool_input, default=str)[:80]}...)")
        
        result = execute_tool(tool_name, tool_input)
        
        if verbose:
            result_preview = result[:100] if isinstance(result, str) else str(result)[:100]
            print(f"  → {result_preview}...")
        
        if show_tools_callback:
            show_tools_callback(tool_name, tool_input, result)
        
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block["id"],
            "content": result,
        })
        
        # Track for edit context
        track_log_operation(tool_name, tool_input, result, recent_logs, logs_this_turn)
    
    return tool_results


def finalize_turn(
    user_message: str,
    response_text: str,
    recent_logs: dict,
    logs_this_turn: dict,
) -> dict:
    """Finalize the turn by updating recent_logs and creating last_exchange.
    
    Args:
        user_message: The user's message this turn.
        response_text: The assistant's final text response.
        recent_logs: Session's recent_logs (modified in place).
        logs_this_turn: New logs created this turn.
    
    Returns:
        New last_exchange dict for next turn's context.
    """
    # Update recent_logs with entries from this turn
    for table, entries in logs_this_turn.items():
        recent_logs[table] = entries
    
    # Create new last_exchange for next turn
    return {
        "user": user_message,
        "assistant": response_text[:500]  # Truncate to avoid bloat
    }
