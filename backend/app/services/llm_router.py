"""
LLM Router - Routes requests to appropriate LLM providers.
Supports: OpenAI, Anthropic, Google, Mistral, Ollama, OpenRouter
"""
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI
from langchain_community.chat_models import ChatOllama

from app.config import (
    settings,
    ExternalURLs,
    Defaults,
    PROVIDER_MODELS,
    SUPPORTED_PROVIDERS,
    Headers,
)


class LLMRouter:
    """
    Routes LLM requests to the appropriate provider.

    Supports:
    - OpenAI (GPT-4, GPT-3.5, etc.)
    - Anthropic (Claude 3.x)
    - Google (Gemini)
    - Mistral
    - Ollama (local models)
    - OpenRouter (unified gateway to 400+ models)
    """

    @staticmethod
    def get_llm(
        provider: str,
        model: str,
        api_key: str,
        temperature: float = Defaults.LLM_TEMPERATURE,
        max_tokens: int = Defaults.LLM_MAX_TOKENS,
        base_url: Optional[str] = None,
        streaming: bool = True,
    ) -> BaseChatModel:
        """
        Get an LLM instance for the specified provider.

        Args:
            provider: Provider name (openai, anthropic, google, mistral, ollama, openrouter)
            model: Model name (e.g., gpt-4o, claude-3-5-sonnet-latest)
            api_key: API key for the provider
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            base_url: Custom base URL (for Ollama or custom endpoints)
            streaming: Whether to enable streaming

        Returns:
            LangChain chat model instance
        """
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")

        match provider:
            case "openai":
                return ChatOpenAI(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    streaming=streaming,
                )

            case "anthropic":
                return ChatAnthropic(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    streaming=streaming,
                )

            case "google":
                return ChatGoogleGenerativeAI(
                    model=model,
                    google_api_key=api_key,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    streaming=streaming,
                )

            case "mistral":
                return ChatMistralAI(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    streaming=streaming,
                )

            case "ollama":
                return ChatOllama(
                    model=model,
                    base_url=base_url or ExternalURLs.OLLAMA_DEFAULT,
                    temperature=temperature,
                    # Ollama doesn't use API key
                )

            case "openrouter":
                # OpenRouter uses OpenAI-compatible API
                return ChatOpenAI(
                    model=model,
                    api_key=api_key,
                    base_url=ExternalURLs.OPENROUTER_API,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    streaming=streaming,
                    default_headers={
                        Headers.OPENROUTER_REFERER: settings.app_url,
                        Headers.OPENROUTER_TITLE: settings.app_name,
                    },
                )

            case _:
                raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def get_available_providers() -> dict[str, list[str]]:
        """Get all available providers and their models."""
        return PROVIDER_MODELS.copy()

    @staticmethod
    def validate_provider_model(provider: str, model: str) -> bool:
        """Check if a model is valid for a provider."""
        if provider not in PROVIDER_MODELS:
            return False

        # For OpenRouter, allow any model format
        if provider == "openrouter":
            return True

        return model in PROVIDER_MODELS[provider]
