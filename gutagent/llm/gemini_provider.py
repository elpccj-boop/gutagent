"""Google Gemini LLM provider using the new google-genai SDK."""

import json
import os
from typing import Generator

from .base import BaseLLMProvider, LLMResponse


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider using the new unified SDK."""
    
    def __init__(self, model: str = "gemini-2.5-flash", api_key: str = None):
        self.model = model
        
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError("google-genai package not installed. Run: pip install google-genai")
        
        # Get API key
        api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")
        
        self.client = genai.Client(api_key=api_key)
        self.types = types
    
    def _convert_tools_to_gemini(self, tools: list) -> list:
        """Convert Anthropic tool format to Gemini function declarations."""
        gemini_tools = []
        for tool in tools:
            gemini_tools.append(
                self.types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    parameters=tool.get("input_schema", {}),
                )
            )
        return gemini_tools
    
    def _convert_messages_to_gemini(self, messages: list) -> list:
        """Convert Anthropic message format to Gemini contents."""
        contents = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            # Gemini uses "user" and "model" roles
            gemini_role = "model" if role == "assistant" else "user"
            
            if role == "user":
                if isinstance(content, list) and content and content[0].get("type") == "tool_result":
                    # Tool results
                    parts = []
                    for tool_result in content:
                        parts.append(
                            self.types.Part.from_function_response(
                                name=tool_result.get("tool_name", "unknown"),
                                response={"result": tool_result["content"]}
                            )
                        )
                    contents.append(self.types.Content(role="user", parts=parts))
                else:
                    text = content if isinstance(content, str) else json.dumps(content)
                    contents.append(self.types.Content(role="user", parts=[self.types.Part.from_text(text=text)]))
            
            elif role == "assistant":
                if isinstance(content, str):
                    contents.append(self.types.Content(role="model", parts=[self.types.Part.from_text(text=content)]))
                elif isinstance(content, list):
                    parts = []
                    for block in content:
                        if block.get("type") == "tool_use":
                            parts.append(
                                self.types.Part.from_function_call(
                                    name=block["name"],
                                    args=block["input"],
                                )
                            )
                        elif block.get("type") == "text" and block.get("text"):
                            parts.append(self.types.Part.from_text(text=block["text"]))
                    if parts:
                        contents.append(self.types.Content(role="model", parts=parts))
        
        return contents
    
    def chat(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat request to Gemini."""
        gemini_tools = self._convert_tools_to_gemini(tools) if tools else None
        contents = self._convert_messages_to_gemini(messages)
        
        # Build config
        config_kwargs = {
            "system_instruction": system_prompt,
            "max_output_tokens": max_tokens,
        }
        if gemini_tools:
            config_kwargs["tools"] = [self.types.Tool(function_declarations=gemini_tools)]
            config_kwargs["automatic_function_calling"] = self.types.AutomaticFunctionCallingConfig(disable=True)
        
        config = self.types.GenerateContentConfig(**config_kwargs)
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        
        # Convert response to standard format
        content = []
        has_tool_calls = False
        
        if response.candidates and response.candidates[0].content:
            parts = response.candidates[0].content.parts
            if parts:  # parts can be None
                for part in parts:
                    if hasattr(part, 'text') and part.text:
                        content.append({"type": "text", "text": part.text})
                    elif hasattr(part, 'function_call') and part.function_call:
                        has_tool_calls = True
                        fc = part.function_call
                        # Convert args to dict
                        args = dict(fc.args) if fc.args else {}
                        content.append({
                            "type": "tool_use",
                            "id": f"tool_{fc.name}",
                            "name": fc.name,
                            "input": args,
                        })
        
        # If no content, provide a fallback message
        if not content:
            content.append({"type": "text", "text": "[No response from model]"})

        stop_reason = "tool_use" if has_tool_calls else "end_turn"

        # Extract token usage if available
        usage = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "input_tokens": getattr(um, 'prompt_token_count', 0) or 0,
                "output_tokens": getattr(um, 'candidates_token_count', 0) or 0,
            }

        return LLMResponse(content=content, stop_reason=stop_reason, usage=usage)
    
    def chat_stream(
        self,
        messages: list,
        system_prompt: str,
        tools: list,
        max_tokens: int = 4096,
    ) -> Generator[dict, None, LLMResponse]:
        """Stream a chat response from Gemini."""
        # For now, use non-streaming and yield all at once
        # Gemini streaming with tools is complex
        response = self.chat(messages, system_prompt, tools, max_tokens)
        
        # Yield text content
        for block in response.content:
            if block.get("type") == "text":
                yield {"type": "text", "content": block["text"]}
            elif block.get("type") == "tool_use":
                yield {"type": "tool_start", "name": block["name"], "id": block["id"]}
        
        return response
    
    def get_model_name(self) -> str:
        return f"gemini/{self.model}"
