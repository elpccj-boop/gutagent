"""OpenAI LLM provider."""

import os
import json
from typing import Generator

from .base import BaseLLMProvider, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider (GPT-4, etc.)."""
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: str = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        # Import here to make openai optional
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")
    
    def _convert_tools_to_openai(self, tools: list) -> list:
        """Convert Anthropic tool format to OpenAI function format."""
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
        """Convert Anthropic message format to OpenAI format."""
        openai_messages = [{"role": "system", "content": system_prompt}]
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "user":
                # Handle tool results
                if isinstance(content, list) and content and content[0].get("type") == "tool_result":
                    for tool_result in content:
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_result["tool_use_id"],
                            "content": tool_result["content"],
                        })
                else:
                    openai_messages.append({"role": "user", "content": content if isinstance(content, str) else json.dumps(content)})
            
            elif role == "assistant":
                if isinstance(content, str):
                    openai_messages.append({"role": "assistant", "content": content})
                elif isinstance(content, list):
                    # Handle tool calls
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
        """Send a chat request to OpenAI."""
        openai_messages = self._convert_messages_to_openai(messages, system_prompt)
        openai_tools = self._convert_tools_to_openai(tools)
        
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=openai_messages,
            tools=openai_tools if openai_tools else None,
        )
        
        # Convert response to standard format
        choice = response.choices[0]
        content = []
        
        if choice.message.content:
            content.append({"type": "text", "text": choice.message.content})
        
        if choice.message.tool_calls:
            for tool_call in choice.message.tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "input": json.loads(tool_call.function.arguments),
                })
        
        # Map finish reason
        stop_reason = "end_turn"
        if choice.finish_reason == "tool_calls":
            stop_reason = "tool_use"
        
        return LLMResponse(content=content, stop_reason=stop_reason)
    
    def chat_stream(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> Generator[dict, None, LLMResponse]:
        """Stream a chat response from OpenAI."""
        openai_messages = self._convert_messages_to_openai(messages, system_prompt)
        openai_tools = self._convert_tools_to_openai(tools)
        
        stream = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=openai_messages,
            tools=openai_tools if openai_tools else None,
            stream=True,
        )
        
        collected_content = []
        current_tool_calls = {}
        current_text = ""
        
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            
            # Text content
            if delta.content:
                current_text += delta.content
                yield {"type": "text", "content": delta.content}
            
            # Tool calls
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    idx = tool_call.index
                    if idx not in current_tool_calls:
                        current_tool_calls[idx] = {
                            "id": tool_call.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    
                    if tool_call.id:
                        current_tool_calls[idx]["id"] = tool_call.id
                    
                    if tool_call.function:
                        if tool_call.function.name:
                            current_tool_calls[idx]["name"] = tool_call.function.name
                            yield {"type": "tool_start", "name": tool_call.function.name, "id": current_tool_calls[idx]["id"]}
                        if tool_call.function.arguments:
                            current_tool_calls[idx]["arguments"] += tool_call.function.arguments
                            yield {"type": "tool_input", "content": tool_call.function.arguments}
        
        # Build final content
        if current_text:
            collected_content.append({"type": "text", "text": current_text})
        
        for idx in sorted(current_tool_calls.keys()):
            tc = current_tool_calls[idx]
            try:
                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            collected_content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": args,
            })
        
        stop_reason = "tool_use" if current_tool_calls else "end_turn"
        return LLMResponse(content=collected_content, stop_reason=stop_reason)
    
    def get_model_name(self) -> str:
        return self.model
