"""
OpenRouter client for unified LLM access.
Provides access to 400+ models via single API with fallback support.
"""
from typing import Optional

from langchain_openai import ChatOpenAI

from app.config import settings, ExternalURLs, Defaults, Headers


class OpenRouterClient:
    """
    OpenRouter client for accessing 400+ LLMs via unified API.

    Features:
    - Single API for all major providers (OpenAI, Anthropic, Google, Meta, etc.)
    - Automatic fallbacks
    - Cost optimization
    - Rate limit handling
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key. Falls back to settings if not provided.
        """
        self.api_key = api_key
        if not self.api_key and settings.openrouter_api_key:
            self.api_key = settings.openrouter_api_key.get_secret_value()

    def get_chat_model(
        self,
        model: str = "openrouter/auto",
        temperature: float = Defaults.LLM_TEMPERATURE,
        max_tokens: int = Defaults.LLM_MAX_TOKENS,
        streaming: bool = True,
        provider_preferences: Optional[dict] = None,
    ) -> ChatOpenAI:
        """
        Get a chat model via OpenRouter.

        Args:
            model: Model identifier (e.g., "openai/gpt-4o", "anthropic/claude-3.5-sonnet")
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            streaming: Enable streaming
            provider_preferences: OpenRouter provider routing preferences

        Returns:
            LangChain ChatOpenAI instance configured for OpenRouter

        Example provider_preferences:
            {
                "allow_fallbacks": True,
                "order": ["Anthropic", "OpenAI"],  # Prefer Anthropic
                "require_parameters": True
            }
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        extra_body = {}
        if provider_preferences:
            extra_body["provider"] = provider_preferences

        return ChatOpenAI(
            model=model,
            api_key=self.api_key,
            base_url=ExternalURLs.OPENROUTER_API,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            model_kwargs={"extra_body": extra_body} if extra_body else {},
            default_headers={
                Headers.OPENROUTER_REFERER: settings.app_url,
                Headers.OPENROUTER_TITLE: settings.app_name,
            },
        )

    def get_model_with_fallback(
        self,
        primary_model: str,
        fallback_models: list[str],
        temperature: float = Defaults.LLM_TEMPERATURE,
        max_tokens: int = Defaults.LLM_MAX_TOKENS,
        streaming: bool = True,
    ) -> ChatOpenAI:
        """
        Get a model with automatic fallbacks.

        If the primary model fails (rate limit, down, etc.),
        OpenRouter automatically tries fallback models.

        Args:
            primary_model: Primary model to use
            fallback_models: List of fallback models in order
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            streaming: Enable streaming

        Returns:
            LangChain ChatOpenAI configured with fallbacks

        Example:
            client.get_model_with_fallback(
                "anthropic/claude-3.5-sonnet",
                ["openai/gpt-4o", "google/gemini-pro-1.5"]
            )
        """
        return self.get_chat_model(
            model=primary_model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            provider_preferences={
                "allow_fallbacks": True,
                "fallbacks": fallback_models,
            },
        )

    def get_auto_model(
        self,
        temperature: float = Defaults.LLM_TEMPERATURE,
        max_tokens: int = Defaults.LLM_MAX_TOKENS,
        streaming: bool = True,
    ) -> ChatOpenAI:
        """
        Get the auto-routed model.

        OpenRouter automatically selects the best model based on:
        - Current availability
        - Performance
        - Cost

        Returns:
            LangChain ChatOpenAI configured for auto-routing
        """
        return self.get_chat_model(
            model="openrouter/auto",
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        )

    @staticmethod
    def get_popular_models() -> list[dict]:
        """Get list of popular OpenRouter models."""
        return [
            {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
            {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
            {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku", "provider": "Anthropic"},
            {"id": "google/gemini-pro-1.5", "name": "Gemini 1.5 Pro", "provider": "Google"},
            {"id": "google/gemini-flash-1.5", "name": "Gemini 1.5 Flash", "provider": "Google"},
            {"id": "meta-llama/llama-3.1-405b-instruct", "name": "Llama 3.1 405B", "provider": "Meta"},
            {"id": "meta-llama/llama-3.1-70b-instruct", "name": "Llama 3.1 70B", "provider": "Meta"},
            {"id": "mistralai/mistral-large", "name": "Mistral Large", "provider": "Mistral"},
            {"id": "openrouter/auto", "name": "Auto (Best)", "provider": "OpenRouter"},
        ]
