"""AI answer providers. Add a new one here to make it swappable via TRADO_LLM_PROVIDER."""

from trado.config import Settings
from trado.llm.base import LlmError, LlmProvider, LlmRateLimitError

__all__ = ["LlmError", "LlmProvider", "LlmRateLimitError", "create_llm_provider"]


def create_llm_provider(settings: Settings) -> LlmProvider:
    name = settings.llm_provider
    if name == "groq":
        from trado.llm.groq_vision import GroqVisionProvider

        return GroqVisionProvider(
            settings.groq_api_key,
            model=settings.llm_model,
            reasoning_effort=settings.llm_reasoning,
        )
    raise LlmError(f"Unknown AI provider '{name}'. Available: groq")
