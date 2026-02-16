"""LiteLLM provider implementation for multi-provider support."""

import json
import json_repair
import os
from typing import Any, AsyncGenerator

import litellm
from litellm import acompletion

from nanofolks.providers.base import LLMProvider, LLMResponse, StreamChunk, ToolCallRequest
from nanofolks.providers.registry import find_by_model, find_gateway
from nanofolks.security.secure_memory import SecureString


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.
    
    Supports OpenRouter, Anthropic, OpenAI, Gemini, MiniMax, and many other providers through
    a unified interface.  Provider-specific logic is driven by the registry
    (see providers/registry.py) — no if-elif chains needed here.
    
    Security: Uses SecureString for API key storage to protect against memory scraping.
    """
    
    def __init__(
        self, 
        api_key: str | None = None, 
        api_base: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
        set_env_vars: bool = False,  # Security: default to False, pass True only if needed
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        
        # Store API key securely using SecureString
        # This protects against memory scraping attacks
        self._secure_key: SecureString | None = None
        if api_key:
            try:
                self._secure_key = SecureString(api_key)
            except Exception:
                # Fall back to plain storage if SecureString fails (e.g., no memory locking)
                self._secure_key = None
        
        # Detect gateway / local deployment.
        # provider_name (from config key) is the primary signal;
        # api_key / api_base are fallback for auto-detection.
        self._gateway = find_gateway(provider_name, api_key, api_base)
        
        # Configure environment variables only if explicitly enabled (security: off by default)
        # API key is passed directly in kwargs to chat(), so env vars are not required
        if set_env_vars and api_key:
            self._setup_env(api_key, api_base, default_model)
        
        if api_base:
            litellm.api_base = api_base
        
        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # Drop unsupported parameters for providers (e.g., gpt-5 rejects some params)
        litellm.drop_params = True
    
    def _get_api_key(self) -> str | None:
        """Get API key from secure storage."""
        if self._secure_key:
            return self._secure_key.get()
        return None
    
    def _get_api_key_bytes(self) -> bytes | None:
        """Get API key bytes from secure storage."""
        if self._secure_key:
            return self._secure_key.get_bytes()
        return None
    
    def __del__(self):
        """Clean up secure key on object destruction."""
        if hasattr(self, '_secure_key') and self._secure_key:
            try:
                self._secure_key.wipe()
            except Exception:
                pass
    
    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        """Set environment variables based on detected provider. Only called if set_env_vars=True."""
        spec = self._gateway or find_by_model(model)
        if not spec:
            return

        # Gateway/local overrides existing env; standard provider doesn't
        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)

        # Resolve env_extras placeholders:
        #   {api_key}  → user's API key
        #   {api_base} → user's api_base, falling back to spec.default_api_base
        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)
    
    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if self._gateway:
            # Gateway mode: apply gateway prefix, skip provider-specific prefixes
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix and not model.startswith(f"{prefix}/"):
                model = f"{prefix}/{model}"
            return model
        
        # Standard mode: auto-prefix for known providers
        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"
        
        return model
    
    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
        
        Returns:
            LLMResponse with content and/or tool calls.
        """
        model = self._resolve_model(model or self.default_model)
        
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # Apply model-specific overrides (e.g. kimi-k2.5 temperature)
        self._apply_model_overrides(model, kwargs)
        
        # Pass api_key directly — more reliable than env vars alone
        # Use secure storage if available
        secure_key = self._get_api_key()
        if secure_key:
            kwargs["api_key"] = secure_key
        elif self.api_key:
            # Fall back to plain storage (shouldn't happen often)
            kwargs["api_key"] = self.api_key
        
        # Pass api_base for custom endpoints
        if self.api_base:
            kwargs["api_base"] = self.api_base
        
        # Pass extra headers (e.g. APP-Code for AiHubMix)
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            # Return error as content for graceful handling
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )
    
    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream a chat completion request via LiteLLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
        
        Yields:
            StreamChunk objects as they arrive.
        """
        model = self._resolve_model(model or self.default_model)
        
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        
        self._apply_model_overrides(model, kwargs)
        
        # Use secure storage if available
        secure_key = self._get_api_key()
        if secure_key:
            kwargs["api_key"] = secure_key
        elif self.api_key:
            kwargs["api_key"] = self.api_key
        
        if self.api_base:
            kwargs["api_base"] = self.api_base
        
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        try:
            response = await acompletion(**kwargs)
            
            accumulated_content = ""
            accumulated_reasoning = ""
            tool_calls_buffer = []
            
            async for chunk in response:
                choice = chunk.choices[0]
                delta = choice.delta
                
                # Accumulate content
                if delta.content:
                    accumulated_content += delta.content
                
                # Accumulate reasoning (for models like DeepSeek-R1)
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    accumulated_reasoning += delta.reasoning_content
                
                # Check for tool calls
                current_tool_calls = []
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc in delta.tool_calls:
                        # Parse arguments
                        args = {}
                        if hasattr(tc.function, "arguments") and tc.function.arguments:
                            if isinstance(tc.function.arguments, str):
                                try:
                                    args = json_repair.loads(tc.function.arguments)
                                except:
                                    args = {"_raw": tc.function.arguments}
                            else:
                                args = tc.function.arguments or {}
                        
                        current_tool_calls.append(ToolCallRequest(
                            id=tc.id or f"call_{len(tool_calls_buffer)}",
                            name=tc.function.name or "",
                            arguments=args,
                        ))
                    tool_calls_buffer.extend(current_tool_calls)
                
                finish_reason = choice.finish_reason
                is_final = finish_reason is not None and finish_reason != "null"
                
                yield StreamChunk(
                    content=accumulated_content,
                    reasoning_content=accumulated_reasoning if accumulated_reasoning else None,
                    tool_calls=current_tool_calls,
                    finish_reason=finish_reason,
                    is_final=is_final,
                )
                
                if is_final:
                    break
                    
        except Exception as e:
            yield StreamChunk(
                content=f"Error calling LLM: {str(e)}",
                is_final=True,
            )
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json_repair.loads(args)
                
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
        
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        reasoning_content = getattr(message, "reasoning_content", None)
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
        )
    
    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
