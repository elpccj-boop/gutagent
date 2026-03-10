#!/usr/bin/env python3
"""
GutAgent - Run the web UI server.

Usage:
    python -m gutagent.run_web              # Start web server on port 8000
    python -m gutagent.run_web --port 3000  # Use a different port
"""

import argparse
import sys
import os

from dotenv import load_dotenv
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description='Run GutAgent web server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run on (default: 8000)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    args = parser.parse_args()
    
    # Check for API key based on provider
    provider = os.getenv('LLM_PROVIDER', 'claude')
    if provider == 'claude' and not os.getenv('ANTHROPIC_API_KEY'):
        print("\n❌ ANTHROPIC_API_KEY not set!")
        print("   Run: export ANTHROPIC_API_KEY='your-key-here'\n")
        sys.exit(1)
    elif provider == 'openai' and not os.getenv('OPENAI_API_KEY'):
        print("\n❌ OPENAI_API_KEY not set!")
        print("   Run: export OPENAI_API_KEY='your-key-here'\n")
        sys.exit(1)

    import uvicorn
    from gutagent.api.server import app
    
    # Get local IP for network access
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "localhost"
    
    # Check auth status
    auth_username = os.getenv("GUTAGENT_USERNAME", "")
    auth_password = os.getenv("GUTAGENT_PASSWORD", "")
    auth_status = "🔒 Auth enabled" if auth_username and auth_password else "⚠️  No auth (set GUTAGENT_USERNAME and GUTAGENT_PASSWORD)"

    print("\n🥗 GutAgent Web UI")
    print(f"   {auth_status}")
    print(f"   Local:   http://localhost:{args.port}")
    print(f"   Network: http://{local_ip}:{args.port}")
    print("\n   Open the network URL on your phone to use as an app!")
    print("   Press Ctrl+C to stop\n")
    
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")

if __name__ == "__main__":
    main()
