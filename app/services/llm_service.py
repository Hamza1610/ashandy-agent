"""
LLM Service: Multi-provider LLM with automatic failover.
Chain: Groq → Together AI → OpenRouter
"""
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from app.utils.config import settings
from enum import Enum
import httpx
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    GROQ = "groq"
    TOGETHER = "together"
    OPENROUTER = "openrouter"


class MultiProviderLLM:
    """LLM service with automatic failover across multiple providers."""
    
    PROVIDER_CONFIG = {
        LLMProvider.GROQ: {
            "key_attr": "LLAMA_API_KEY",
            "base_url": None,
            "models": {
                "fast": "meta-llama/llama-4-scout-17b-16e-instruct",
                "powerful": "meta-llama/llama-4-maverick-17b-128e-instruct",
                "guard": "meta-llama/llama-guard-4-12b",
                "versatile": "llama-3.3-70b-versatile"
            },
            "timeout": 30
        },
        LLMProvider.TOGETHER: {
            "key_attr": "TOGETHER_API_KEY",
            "base_url": "https://api.together.xyz/v1",
            "models": {
                "fast": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "powerful": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "guard": "meta-llama/Llama-Guard-3-8B",
                "versatile": "meta-llama/Llama-3.3-70B-Instruct-Turbo"
            },
            "timeout": 45
        },
        LLMProvider.OPENROUTER: {
            "key_attr": "OPENROUTER_API_KEY",
            "base_url": "https://openrouter.ai/api/v1",
            "models": {
                "fast": "meta-llama/llama-3.3-70b-instruct",
                "powerful": "meta-llama/llama-3.3-70b-instruct",
                "guard": "meta-llama/llama-guard-2-8b", 
                "versatile": "meta-llama/llama-3.3-70b-instruct"
            },
            "timeout": 60
        }
    }
    
    def __init__(self):
        self.providers = [LLMProvider.GROQ, LLMProvider.TOGETHER, LLMProvider.OPENROUTER]
        self.failure_counts = {p: 0 for p in self.providers}
        self.max_failures_before_skip = 3
    
    def _get_api_key(self, provider: LLMProvider) -> Optional[str]:
        """Get API key for a provider."""
        key_attr = self.PROVIDER_CONFIG[provider]["key_attr"]
        return getattr(settings, key_attr, None)
    
    def _get_ordered_providers(self) -> List[LLMProvider]:
        """Order providers by failure count (least failures first), skip if too many failures."""
        available = [
            p for p in self.providers 
            if self._get_api_key(p) and self.failure_counts[p] < self.max_failures_before_skip
        ]
        return sorted(available, key=lambda p: self.failure_counts[p])
    
    async def invoke(
        self, 
        messages: List[Tuple[str, str]], 
        model_type: str = "fast",
        temperature: float = 0.3,
        json_mode: bool = False
    ) -> str:
        """
        Invoke LLM with automatic failover.
        
        Args:
            messages: List of (role, content) tuples
            model_type: "fast", "powerful", "guard", or "versatile"
            temperature: 0.0-1.0
            json_mode: Request JSON output format
            
        Returns:
            LLM response content
        """
        ordered_providers = self._get_ordered_providers()
        
        if not ordered_providers:
            logger.error("No LLM providers available!")
            return self._graceful_fallback_response()
        
        last_error = None
        for provider in ordered_providers:
            try:
                config = self.PROVIDER_CONFIG[provider]
                model_name = config["models"].get(model_type, config["models"]["fast"])
                
                logger.info(f"LLM call: {provider.value} / {model_name}")
                
                response = await self._call_provider(
                    provider=provider,
                    messages=messages,
                    model=model_name,
                    temperature=temperature,
                    timeout=config["timeout"],
                    json_mode=json_mode
                )
                
                # Success - reset failure count
                self.failure_counts[provider] = 0
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"{provider.value} failed: {type(e).__name__}: {e}")
                self.failure_counts[provider] += 1
                continue
        
        # All providers failed
        logger.error(f"All LLM providers failed! Last error: {last_error}")
        return self._graceful_fallback_response()
    
    async def _call_provider(
        self, 
        provider: LLMProvider, 
        messages: List[Tuple[str, str]],
        model: str, 
        temperature: float, 
        timeout: int,
        json_mode: bool = False
    ) -> str:
        """Call a specific provider."""
        
        if provider == LLMProvider.GROQ:
            return await self._call_groq(messages, model, temperature, timeout, json_mode)
        else:
            return await self._call_openai_compatible(
                provider, messages, model, temperature, timeout, json_mode
            )
    
    async def _call_groq(
        self, 
        messages: List[Tuple[str, str]], 
        model: str, 
        temperature: float, 
        timeout: int,
        json_mode: bool
    ) -> str:
        """Call Groq via LangChain."""
        model_kwargs = {}
        if json_mode:
            model_kwargs["response_format"] = {"type": "json_object"}
        
        # Build kwargs dynamically to avoid passing None
        groq_kwargs = {
            "groq_api_key": settings.LLAMA_API_KEY,
            "model_name": model,
            "temperature": temperature,
            "timeout": timeout,
        }
        if model_kwargs:
            groq_kwargs["model_kwargs"] = model_kwargs
        
        llm = ChatGroq(**groq_kwargs)
        
        # Convert tuples to LangChain messages
        lc_messages = []
        for role, content in messages:
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        
        response = await llm.ainvoke(lc_messages)
        return response.content
    
    async def _call_openai_compatible(
        self, 
        provider: LLMProvider,
        messages: List[Tuple[str, str]], 
        model: str, 
        temperature: float, 
        timeout: int,
        json_mode: bool
    ) -> str:
        """Call OpenAI-compatible API (Together, OpenRouter)."""
        config = self.PROVIDER_CONFIG[provider]
        api_key = self._get_api_key(provider)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # OpenRouter-specific headers
        if provider == LLMProvider.OPENROUTER:
            headers["HTTP-Referer"] = "https://ashandy-agent.com"
            headers["X-Title"] = "Ashandy Cosmetics Agent"
        
        # Build payload
        payload = {
            "model": model,
            "messages": [{"role": role, "content": content} for role, content in messages],
            "temperature": temperature
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{config['base_url']}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    def _graceful_fallback_response(self) -> str:
        """Return when all providers fail."""
        return (
            "I'm experiencing technical difficulties right now. "
            "Please try again in a moment, or contact us directly at the store. "
            "We're at Divine Favor Plaza, Iyaganku, Ibadan. "
            "Phone: Check our Instagram @ashandy_cosmetics. Thank you for your patience! 🙏"
        )
    
    def reset_failure_counts(self):
        """Reset all failure counts (call periodically or on successful health check)."""
        self.failure_counts = {p: 0 for p in self.providers}
    
    async def health_check(self) -> dict:
        """Check health of all providers."""
        status = {}
        for provider in self.providers:
            if not self._get_api_key(provider):
                status[provider.value] = "not_configured"
                continue
            
            try:
                response = await self._call_provider(
                    provider=provider,
                    messages=[("user", "Say OK")],
                    model=self.PROVIDER_CONFIG[provider]["models"]["fast"],
                    temperature=0,
                    timeout=10,
                    json_mode=False
                )
                status[provider.value] = "up" if response else "degraded"
            except Exception as e:
                status[provider.value] = f"down: {type(e).__name__}"
        
        return status


# Singleton instance
llm_service = MultiProviderLLM()


def get_llm(model_type: str = "fast", temperature: float = 0.3, json_mode: bool = False) -> ChatGroq:
    """
    Get a LangChain-compatible ChatGroq LLM for use with bind_tools.
    
    This function returns the primary Groq LLM while the llm_service.invoke() 
    provides the full failover chain. Use this for agents that need tools.
    
    Args:
        model_type: "fast", "powerful", "guard", or "versatile"
        temperature: 0.0-1.0
        json_mode: Request JSON output format
        
    Returns:
        ChatGroq instance
    """
    config = MultiProviderLLM.PROVIDER_CONFIG[LLMProvider.GROQ]
    model_name = config["models"].get(model_type, config["models"]["fast"])
    
    model_kwargs = {}
    if json_mode:
        model_kwargs["response_format"] = {"type": "json_object"}
    
    # Build kwargs dynamically to avoid passing None
    groq_kwargs = {
        "groq_api_key": settings.LLAMA_API_KEY,
        "model_name": model_name,
        "temperature": temperature,
        "timeout": config["timeout"],
    }
    if model_kwargs:
        groq_kwargs["model_kwargs"] = model_kwargs
    
    return ChatGroq(**groq_kwargs)


async def invoke_with_fallback(
    messages: List[Tuple[str, str]], 
    model_type: str = "fast",
    temperature: float = 0.3,
    json_mode: bool = False
) -> str:
    """
    Convenience function to invoke LLM with full failover.
    Use this for simple text generation without tool binding.
    """
    return await llm_service.invoke(messages, model_type, temperature, json_mode)

