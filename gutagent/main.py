#!/usr/bin/env python3
"""GutAgent — Personalized Dietary AI Agent (CLI Interface)."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gutagent.agent import run_agent
from gutagent.profile import load_profile
from gutagent.db.models import init_db
from gutagent.config import MODEL, MODEL_HAIKU

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
            "Type [bold]quit[/bold] or [bold]exit[/bold] to end the session.\n\n"
            "[bold]Commands:[/bold]\n"
            "  --verbose  Show tool calls\n"
            "  --quiet    Hide tool calls (default)\n"
            "  --haiku    Use Haiku (cheaper)\n"
            "  --sonnet   Use Sonnet (default)\n\n"
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
        print("  Type 'quit' or 'exit' to end.")
        print()
        print("  Commands:")
        print("    --verbose  Show tool calls")
        print("    --quiet    Hide tool calls (default)")
        print("    --haiku    Use Haiku (cheaper)")
        print("    --sonnet   Use Sonnet (default)")
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
            "[bold]Commands:[/bold] --verbose, --quiet, --haiku, --sonnet",
            border_style="green",
        ))
    else:
        print("\n" + "=" * 60)
        print("  GutAgent — Your Personalized Dietary Assistant")
        print("=" * 60)
        print("  Tell me what you ate, how you're feeling,")
        print("  or ask for meal suggestions.")
        print("  Type 'quit' or 'exit' to end.")
        print("  Commands: --verbose, --quiet, --haiku, --sonnet")
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
    
    if "error" in profile:
        print(f"⚠️  {profile['error']}")
        print("Creating a minimal profile to get started...\n")
        profile = {"note": "No profile loaded. Responses will be generic."}
    
    conversation_history = []
    verbose = False
    current_model = MODEL

    print_welcome()
    
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
        
        if user_input.lower() in ("quit", "exit", "bye"):
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

        # Model commands
        if user_input == "--haiku":
            current_model = MODEL_HAIKU
            print("Model: Haiku")
            continue

        if user_input == "--sonnet":
            current_model = MODEL
            print("Model: Sonnet")
            continue
        
        try:
            response = run_agent(
                user_message=user_input,
                conversation_history=conversation_history,
                profile=profile,
                verbose=verbose,
                model=current_model,
            )
            
            if HAS_RICH:
                console.print("[bold green]GutAgent:[/bold green]")
            else:
                print("GutAgent:")
            
            print_response(response)
            
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                print("\n❌ API key not set. Run: export ANTHROPIC_API_KEY='your-key-here'\n")
            elif "credit balance" in error_msg.lower():
                print("\n❌ Out of API credits. Add credits or use --haiku for cheaper model.\n")
            else:
                print(f"\n❌ Error: {error_msg}\n")
                if verbose:
                    import traceback
                    traceback.print_exc()


if __name__ == "__main__":
    main()
