import asyncio
import os

import openai

from inference.providers import Provider


class OpenRouterProvider(Provider):
    """OpenRouter provider — OpenAI-compatible API at openrouter.ai."""

    def __init__(self, api_key: str = None, **kwargs):
        api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

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
        max_retries = 6
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_completion_tokens,
                )
                return response.choices[0].message.content
            except (openai.RateLimitError, openai.APIStatusError) as e:
                if isinstance(e, openai.APIStatusError) and e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
        # Final attempt — let any exception propagate.
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
        )
        return response.choices[0].message.content
