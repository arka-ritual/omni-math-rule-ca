import asyncio
import os

import openai

from inference.providers import Provider
from inference.providers.openai_provider import _chat_response_to_meta


class OpenRouterProvider(Provider):
    """OpenRouter provider — OpenAI-compatible API at openrouter.ai."""

    def __init__(self, api_key: str = None, openrouter_provider: str = None, **kwargs):
        api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        # Optional OpenRouter sub-provider routing (e.g. force "DeepSeek" for
        # deepseek/* models). When set, OpenRouter routes only to that
        # upstream and does not silently fall back to a different host.
        # See https://openrouter.ai/docs/features/provider-routing
        if openrouter_provider:
            self._extra_body = {
                "provider": {
                    "order": [openrouter_provider],
                    "allow_fallbacks": False,
                }
            }
        else:
            self._extra_body = None

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "anthropic/claude-opus-4-6",
        temperature: float = 0,
        max_completion_tokens: int = 32768,
        **kwargs,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        create_kwargs = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
        )
        if self._extra_body is not None:
            create_kwargs["extra_body"] = self._extra_body
        max_retries = 6
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(**create_kwargs)
                return response.choices[0].message.content
            except (openai.RateLimitError, openai.APIStatusError) as e:
                if isinstance(e, openai.APIStatusError) and e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
        # Final attempt — let any exception propagate.
        response = await self.client.chat.completions.create(**create_kwargs)
        return response.choices[0].message.content

    async def generate_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "anthropic/claude-opus-4-6",
        temperature: float = 0,
        max_completion_tokens: int = 32768,
        **kwargs,
    ) -> dict:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        create_kwargs = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
        )
        if self._extra_body is not None:
            create_kwargs["extra_body"] = self._extra_body
        max_retries = 6
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(**create_kwargs)
                return self._with_upstream(response)
            except (openai.RateLimitError, openai.APIStatusError) as e:
                if isinstance(e, openai.APIStatusError) and e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
        response = await self.client.chat.completions.create(**create_kwargs)
        return self._with_upstream(response)

    @staticmethod
    def _with_upstream(response) -> dict:
        """Standard metadata plus the upstream that actually served the request.

        OpenRouter echoes the serving provider (e.g. "Novita", "StreamLake") in
        a non-standard top-level `provider` field. When routing is left free —
        no `order` pin — the upstream, and with it the quantization (fp4 vs
        fp8), is chosen per request. Recording it per item means an unpinned run
        can still be audited after the fact: we can report the upstream mix, and
        detect if a cell was served by several.
        """
        meta = _chat_response_to_meta(response)
        meta["upstream_provider"] = getattr(response, "provider", None)
        return meta
