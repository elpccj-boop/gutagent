"""Ollama (local models) LLM provider."""

import json
from typing import Generator

from .base import BaseLLMProvider, LLMResponse


class OllamaProvider(BaseLLMProvider):
    """Ollama provider for local models."""
    
    def __init__(self, model: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        
        # Import here to make ollama optional
        try:
            import ollama
            self.client = ollama.Client(host=host)
        except ImportError:
            raise ImportError("ollama package not installed. Run: pip install ollama")
    
    def _fix_json_string_arguments(self, arguments: dict) -> dict:
        """
        Fix arguments where nested objects/arrays are JSON strings.
        Ollama sometimes returns '["item"]' instead of ["item"].
        """
        fixed = {}
        for key, value in arguments.items():
            if isinstance(value, str):
                # Try to parse JSON strings
                if value.startswith('[') or value.startswith('{'):
                    try:
                        fixed[key] = json.loads(value)
                    except json.JSONDecodeError:
                        fixed[key] = value
                elif value == 'null':
                    fixed[key] = None
                else:
                    fixed[key] = value
            else:
                fixed[key] = value
        return fixed

    def _convert_tools_to_ollama(self, tools: list) -> list:
        """Convert Anthropic tool format to Ollama format."""
        ollama_tools = []
        for tool in tools:
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            })
        return ollama_tools
    
    def _convert_messages_to_ollama(self, messages: list, system_prompt: str) -> list:
        """Convert Anthropic message format to Ollama format."""
        ollama_messages = [{"role": "system", "content": system_prompt}]
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "user":
                # Handle tool results
                if isinstance(content, list) and content and content[0].get("type") == "tool_result":
                    for tool_result in content:
                        ollama_messages.append({
                            "role": "tool",
                            "content": tool_result["content"],
                        })
                else:
                    ollama_messages.append({
                        "role": "user",
                        "content": content if isinstance(content, str) else json.dumps(content)
                    })
            
            elif role == "assistant":
                if isinstance(content, str):
                    ollama_messages.append({"role": "assistant", "content": content})
                elif isinstance(content, list):
                    # Handle tool calls
                    tool_calls = []
                    text_content = ""
                    for block in content:
                        if block.get("type") == "tool_use":
                            tool_calls.append({
                                "function": {
                                    "name": block["name"],
                                    "arguments": block["input"],
                                }
                            })
                        elif block.get("type") == "text":
                            text_content += block.get("text", "")
                    
                    msg_dict = {"role": "assistant", "content": text_content}
                    if tool_calls:
                        msg_dict["tool_calls"] = tool_calls
                    ollama_messages.append(msg_dict)
        
        return ollama_messages
    
    def chat(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat request to Ollama."""
        ollama_messages = self._convert_messages_to_ollama(messages, system_prompt)
        ollama_tools = self._convert_tools_to_ollama(tools) if tools else None
        
        response = self.client.chat(
            model=self.model,
            messages=ollama_messages,
            tools=ollama_tools,
            options={"num_predict": max_tokens},
        )
        
        # Convert response to standard format
        # Ollama returns an object with attributes, not a dict
        content = []
        message = response.message
        
        if message.content:
            content.append({"type": "text", "text": message.content})
        
        if message.tool_calls:
            for i, tool_call in enumerate(message.tool_calls):
                # Fix JSON string arguments
                arguments = self._fix_json_string_arguments(tool_call.function.arguments)
                content.append({
                    "type": "tool_use",
                    "id": f"tool_{i}",
                    "name": tool_call.function.name,
                    "input": arguments,
                })
        
        stop_reason = "tool_use" if message.tool_calls else "end_turn"
        return LLMResponse(content=content, stop_reason=stop_reason)
    
    def chat_stream(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> Generator[dict, None, LLMResponse]:
        """Stream a chat response from Ollama."""
        ollama_messages = self._convert_messages_to_ollama(messages, system_prompt)
        ollama_tools = self._convert_tools_to_ollama(tools) if tools else None
        
        stream = self.client.chat(
            model=self.model,
            messages=ollama_messages,
            tools=ollama_tools,
            options={"num_predict": max_tokens},
            stream=True,
        )
        
        collected_text = ""
        tool_calls = []
        
        for chunk in stream:
            message = chunk.message
            
            # Text content
            if message.content:
                collected_text += message.content
                yield {"type": "text", "content": message.content}
            
            # Tool calls (usually come at the end, not streamed)
            if message.tool_calls:
                for i, tool_call in enumerate(message.tool_calls):
                    # Fix JSON string arguments
                    arguments = self._fix_json_string_arguments(tool_call.function.arguments)
                    tool_calls.append({
                        "type": "tool_use",
                        "id": f"tool_{i}",
                        "name": tool_call.function.name,
                        "input": arguments,
                    })
                    yield {"type": "tool_start", "name": tool_call.function.name, "id": f"tool_{i}"}
        
        # Build final content
        content = []
        if collected_text:
            content.append({"type": "text", "text": collected_text})
        content.extend(tool_calls)
        
        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(content=content, stop_reason=stop_reason)
    
    def get_model_name(self) -> str:
        return f"ollama/{self.model}"
