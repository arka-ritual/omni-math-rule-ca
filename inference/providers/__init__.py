from abc import ABC, abstractmethod


class Provider(ABC):
    """Base class for LLM API providers."""

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate a completion given system and user prompts.

        Args:
            system_prompt: The system-level instruction.
            user_prompt: The user message (math problem).
            **kwargs: Provider-specific options (temperature, max_tokens, etc.).

        Returns:
            The model's response text.
        """

    async def generate_with_meta(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> dict:
        """Like `generate` but returns a dict with metadata.

        Returns a dict with at least:
          - "text": str — the model's response text
          - "completion_tokens": int | None — output tokens consumed
          - "prompt_tokens": int | None — input tokens consumed
          - "finish_reason": str | None — normalized finish reason
              ("stop" | "length" | "content_filter" | "other")

        `finish_reason == "length"` indicates the response was cut by
        the max-token budget; the evaluator uses this to mark such
        responses as `indeterminate` rather than `abstained`.

        Default implementation calls `generate()` and returns null
        metadata. Concrete providers should override this to populate
        the metadata fields from the API response.
        """
        text = await self.generate(system_prompt, user_prompt, **kwargs)
        return {
            "text": text,
            "completion_tokens": None,
            "prompt_tokens": None,
            "finish_reason": None,
        }


_REGISTRY: dict[str, type[Provider]] = {}


def register_provider(name: str, cls: type[Provider]):
    _REGISTRY[name] = cls


def get_provider(name: str, **kwargs) -> Provider:
    """Instantiate a registered provider by name."""
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[name](**kwargs)


# Auto-register bundled providers on import.
from inference.providers.openai_provider import OpenAIProvider  # noqa: E402
from inference.providers.anthropic_provider import AnthropicProvider  # noqa: E402
from inference.providers.google_provider import GoogleProvider  # noqa: E402
from inference.providers.openrouter_provider import OpenRouterProvider  # noqa: E402
from inference.providers.vllm_provider import VLLMProvider  # noqa: E402

register_provider("openai", OpenAIProvider)
register_provider("anthropic", AnthropicProvider)
register_provider("google", GoogleProvider)
register_provider("openrouter", OpenRouterProvider)
register_provider("vllm", VLLMProvider)
