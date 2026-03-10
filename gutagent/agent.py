"""Core agent loop — the heart of GutAgent."""

from gutagent.tools.registry import execute_tool
from gutagent.prompts.system import build_system_prompt
from gutagent.config import TOOLS, MAX_TOKENS, LLM_PROVIDER, get_model_for_tier
from gutagent.llm import get_provider


def run_agent(
    user_message: str,
    conversation_history: list,
    profile: dict,
    verbose: bool = False,
    model: str = None,
    provider: str = None,
) -> str:
    """
    Core agent loop:
    
    1. Send user message + conversation history + tools to LLM
    2. If LLM wants to use a tool → execute it → feed result back
    3. Repeat until LLM produces a final text response
    4. Return the response text
    
    This is intentionally built without any framework so you can see
    exactly what's happening at each step.
    """
    
    system_prompt = build_system_prompt(profile)
    
    # Use passed model or default for current provider
    if model is None:
        model = get_model_for_tier("default")

    # Get LLM provider
    provider_name = provider or LLM_PROVIDER
    llm = get_provider(provider_name, model=model)

    if verbose:
        print(f"  [Using {llm.get_model_name()}]")

    # Add the new user message
    conversation_history.append({
        "role": "user",
        "content": user_message,
    })
    
    # Agent loop — keeps going until LLM gives a text response
    max_iterations = 10  # Safety valve to prevent infinite loops
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        if verbose:
            print(f"  [Agent iteration {iteration}]")
        
        # Call LLM
        response = llm.chat(
            messages=conversation_history,
            system_prompt=system_prompt,
            tools=TOOLS,
            max_tokens=MAX_TOKENS,
        )
        
        if verbose:
            print(f"  [Stop reason: {response.stop_reason}]")
        
        if response.stop_reason == "tool_use":
            # LLM wants to use one or more tools.
            # Add LLM's full response to history
            conversation_history.append({
                "role": "assistant",
                "content": response.content,
            })
            
            # Execute each tool and collect results
            tool_results = []
            for block in response.get_tool_calls():
                if verbose:
                    print(f"  🔧 {block['name']}({block['input']})")

                result = execute_tool(block["name"], block["input"])

                if verbose:
                    # Truncate long results for display
                    display = result[:200] + "..." if len(result) > 200 else result
                    print(f"  → {display}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result,
                })
            
            # Feed tool results back to LLM
            conversation_history.append({
                "role": "user",
                "content": tool_results,
            })
            
            # Loop continues — LLM will process results
            
        else:
            # LLM produced a final text response
            assistant_message = response.get_text()
            
            conversation_history.append({
                "role": "assistant",
                "content": assistant_message,
            })
            
            return assistant_message
    
    # Safety: if we hit max iterations, return what we have
    return "[Agent reached maximum iterations. This usually means a tool is returning unexpected results.]"
