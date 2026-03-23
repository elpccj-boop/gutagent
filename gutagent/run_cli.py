#!/usr/bin/env python3
"""
GutAgent — Personalized Dietary AI Agent (CLI Interface).

Usage:
    python -m gutagent.run_cli
"""

import sys
import os

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gutagent.agent import run_agent
from gutagent.profile import load_profile
from gutagent.db import init_db, set_rda_targets
from gutagent.config import get_model_for_tier, LLM_PROVIDER

# Try to use rich for pretty output, fall back to plain text
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def print_welcome_long():
    if HAS_RICH:
        console.print(Panel(
  "[bold green]GutAgent[/bold green] — Your Personalized Dietary Assistant\n\n"
            "Tell me what you ate, how you're feeling, or ask for meal suggestions.\n"
            "Type [bold]q[/bold] or [bold]quit[/bold] or [bold]x[/bold] or [bold]exit[/bold] to end the session.\n\n"
            "[bold]Commands:[/bold]\n"
            "  --verbose  Show tool calls\n"
            "  --quiet    Hide tool calls (default)\n"
            "  --default  Use Default model (faster)\n"
            "  --smart    Use Smart model (better)\n\n"
            "[bold]Log data[/bold] — just tell me naturally:\n"
            "  'I had eggs and mutton for lunch'\n"
            "  'Feeling bloated, about a 6'\n"
            "  'BP this morning was 138/85 pulse 72'\n"
            "  'I stopped taking Armodafinil on Feb 26'\n\n"
            "[bold]Ask questions:[/bold]\n"
            "  'What have I eaten this week?'\n"
            "  'How is my BP trending?'\n"
            "  'Do you see any patterns in my symptoms?'\n"
            "  'What do you know about me?'\n\n"
            "[bold]Fix data:[/bold]\n"
            "  'Change that severity to 4'\n"
            "  'Delete that last entry'\n",
            border_style="green"
        ))
    else:
        print("\n" + "=" * 60)
        print("  GutAgent — Your Personalized Dietary Assistant")
        print("=" * 60)
        print("  Tell me what you ate, how you're feeling,")
        print("  or ask for meal suggestions.")
        print("  Type 'q' or 'quit' or 'x' or 'exit' to end.")
        print()
        print("  Commands:")
        print("    --verbose  Show tool calls")
        print("    --quiet    Hide tool calls (default)")
        print("    --default  Use Default model (faster)")
        print("    --smart    Use Smart model (better)")
        print()
        print("  Log data — just tell me naturally:")
        print("    'I had eggs and mutton for lunch'")
        print("    'Feeling bloated, about a 6'")
        print("    'BP this morning was 138/85 pulse 72'")
        print("    'I stopped taking Armodafinil on Feb 26'")
        print()
        print("  Ask questions:")
        print("    'What have I eaten this week?'")
        print("    'How is my BP trending?'")
        print("    'Do you see any patterns in my symptoms?'")
        print("    'What do you know about me?'")
        print()
        print("  Fix data:")
        print("    'Change that severity to 4'")
        print("    'Delete that last entry'")
        print("=" * 60 + "\n")


def print_welcome():
    if HAS_RICH:
        console.print(Panel(
            "[bold green]GutAgent[/bold green] — Your Personalized Dietary Assistant\n\n"
            "Tell me what you ate, how you're feeling, or ask for meal suggestions.\n"
            "Type [bold]quit[/bold] or [bold]exit[/bold] to end the session.\n\n"
            "[bold]Commands:[/bold] --verbose, --quiet, --default, --smart",
            border_style="green",
        ))
    else:
        print("\n" + "=" * 60)
        print("  GutAgent — Your Personalized Dietary Assistant")
        print("=" * 60)
        print("  Tell me what you ate, how you're feeling,")
        print("  or ask for meal suggestions.")
        print("  Type 'quit' or 'exit' to end.")
        print("  Commands: --verbose, --quiet, --default, --smart")
        print("=" * 60 + "\n")


def print_response(text: str):
    if HAS_RICH:
        console.print()
        console.print(Markdown(text))
        console.print()
    else:
        print(f"\n{text}\n")


def main():
    # Initialize
    init_db()
    profile = load_profile()
    set_rda_targets(profile)
    
    if "error" in profile:
        print(f"⚠️  {profile['error']}")
        print("Creating a minimal profile to get started...\n")
        profile = {"note": "No profile loaded. Responses will be generic."}
    
    recent_logs = {}  # Tracks recently logged entries for edit context
    last_exchange = {}  # Tracks last Q&A for follow-up context
    verbose = False
    current_tier = "default"  # "default" or "smart"

    print_welcome()
    print(f"  Provider: {LLM_PROVIDER} | Model: {get_model_for_tier(current_tier)}\n")

    while True:
        try:
            if HAS_RICH:
                user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
            else:
                user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! Remember to eat well. 💚")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ("q", "quit", "x", "exit", "bye"):
            print("Goodbye! Remember to eat well. 💚")
            break
        
        # Verbose commands
        if user_input == "--verbose":
            verbose = True
            print("Verbose: ON")
            continue

        if user_input == "--quiet":
            verbose = False
            print("Verbose: OFF")
            continue

        # Model tier commands
        if user_input == "--default":
            current_tier = "default"
            print(f"Model: {get_model_for_tier(current_tier)}")
            continue

        if user_input == "--smart":
            current_tier = "smart"
            print(f"Model: {get_model_for_tier(current_tier)}")
            continue
        
        try:
            if verbose:
                print(f"\n--- INPUT TO AGENT ---")
                if last_exchange:
                    user_preview = last_exchange.get('user', '')[:50]
                    asst_preview = last_exchange.get('assistant', '')[:50]
                    asst_len = len(last_exchange.get('assistant', ''))
                    print(f"  [last_exchange.user: {user_preview}...]")
                    print(f"  [last_exchange.assistant ({asst_len} chars, max 500): {asst_preview}...]")
                else:
                    print(f"  [last_exchange: (empty)]")
                if recent_logs:
                    for table, entries in recent_logs.items():
                        print(f"  [recent_logs.{table}: {len(entries)} entries]")
                else:
                    print(f"  [recent_logs: (empty)]")

            response, recent_logs, last_exchange = run_agent(
                user_message=user_input,
                profile=profile,
                recent_logs=recent_logs,
                last_exchange=last_exchange,
                verbose=verbose,
                model=get_model_for_tier(current_tier),
            )
            
            if HAS_RICH:
                console.print("[bold green]GutAgent:[/bold green]")
            else:
                print("GutAgent:")
            
            print_response(response)
            
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                print(f"\n❌ API key not set. Run: export {LLM_PROVIDER.upper()}_API_KEY='your-key-here'\n")
            elif "credit balance" in error_msg.lower():
                print("\n❌ Out of API credits. Add credits or use --default for cheaper model.\n")
            else:
                print(f"\n❌ Error: {error_msg}\n")
                if verbose:
                    import traceback
                    traceback.print_exc()


if __name__ == "__main__":
    main()
