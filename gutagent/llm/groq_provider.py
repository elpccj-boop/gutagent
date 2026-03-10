"""Groq LLM provider — fast inference for open models."""

import json
from typing import Generator

from .base import BaseLLMProvider, LLMResponse


class GroqProvider(BaseLLMProvider):
    """Groq provider for fast cloud inference of open models."""
    
    def __init__(self, model: str = "llama-3.1-70b-versatile", api_key: str = None):
        self.model = model
        
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("groq package not installed. Run: pip install groq")
        
        self.client = Groq(api_key=api_key)  # Uses GROQ_API_KEY env var if not passed
    
    def _convert_tools_to_openai(self, tools: list) -> list:
        """Convert Anthropic tool format to OpenAI/Groq format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            })
        return openai_tools
    
    def _convert_messages_to_openai(self, messages: list, system_prompt: str) -> list:
        """Convert Anthropic message format to OpenAI/Groq format."""
        openai_messages = [{"role": "system", "content": system_prompt}]
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "user":
                if isinstance(content, list) and content and content[0].get("type") == "tool_result":
                    # Tool results need to be sent as tool messages
                    for tool_result in content:
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_result["tool_use_id"],
                            "content": tool_result["content"],
                        })
                else:
                    openai_messages.append({
                        "role": "user",
                        "content": content if isinstance(content, str) else json.dumps(content)
                    })
            
            elif role == "assistant":
                if isinstance(content, str):
                    openai_messages.append({"role": "assistant", "content": content})
                elif isinstance(content, list):
                    tool_calls = []
                    text_content = ""
                    for block in content:
                        if block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block["id"],
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block["input"]),
                                }
                            })
                        elif block.get("type") == "text":
                            text_content += block.get("text", "")
                    
                    msg_dict = {"role": "assistant", "content": text_content or None}
                    if tool_calls:
                        msg_dict["tool_calls"] = tool_calls
                    openai_messages.append(msg_dict)
        
        return openai_messages
    
    def chat(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat request to Groq."""
        openai_messages = self._convert_messages_to_openai(messages, system_prompt)
        openai_tools = self._convert_tools_to_openai(tools) if tools else None
        
        kwargs = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"
        
        response = self.client.chat.completions.create(**kwargs)
        
        # Convert response to standard format
        content = []
        message = response.choices[0].message
        
        if message.content:
            content.append({"type": "text", "text": message.content})
        
        if message.tool_calls:
            for tool_call in message.tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "input": json.loads(tool_call.function.arguments),
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
        """Stream a chat response from Groq."""
        openai_messages = self._convert_messages_to_openai(messages, system_prompt)
        openai_tools = self._convert_tools_to_openai(tools) if tools else None
        
        kwargs = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"
        
        stream = self.client.chat.completions.create(**kwargs)
        
        collected_text = ""
        tool_calls = {}  # id -> {name, arguments}
        
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            
            # Text content
            if delta.content:
                collected_text += delta.content
                yield {"type": "text", "content": delta.content}
            
            # Tool calls (streamed incrementally)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": tc.id, "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls[idx]["name"] = tc.function.name
                            yield {"type": "tool_start", "name": tc.function.name, "id": tc.id}
                        if tc.function.arguments:
                            tool_calls[idx]["arguments"] += tc.function.arguments
        
        # Build final content
        content = []
        if collected_text:
            content.append({"type": "text", "text": collected_text})
        
        for tc in tool_calls.values():
            try:
                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": args,
            })
        
        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(content=content, stop_reason=stop_reason)
    
    def get_model_name(self) -> str:
        return f"groq/{self.model}"
