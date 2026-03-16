import asyncio
import openai
from inference.providers import Provider

# Models that require the Responses API instead of Chat Completions.
RESPONSES_API_MODELS = {"gpt-5.2-pro", "gpt-5.2-codex"}


class OpenAIProvider(Provider):
    """OpenAI provider supporting both Chat Completions and Responses APIs."""

    def __init__(self, api_key: str = None, **kwargs):
        self.client = openai.AsyncOpenAI(api_key=api_key)  # falls back to OPENAI_API_KEY env var

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "gpt-5.2",
        temperature: float = 0,
        max_completion_tokens: int = 32768,
        **kwargs,
    ) -> str:
        if model in RESPONSES_API_MODELS:
            return await self._generate_responses(
                system_prompt, user_prompt,
                model=model, temperature=temperature,
                max_completion_tokens=max_completion_tokens,
            )
        return await self._generate_chat(
            system_prompt, user_prompt,
            model=model, temperature=temperature,
            max_completion_tokens=max_completion_tokens,
        )

    async def _generate_chat(
        self, system_prompt, user_prompt, *, model, temperature, max_completion_tokens,
    ) -> str:
        """Chat Completions API (gpt-5.2, gpt-4o, etc.)."""
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

    async def _generate_responses(
        self, system_prompt, user_prompt, *, model, temperature, max_completion_tokens,
    ) -> str:
        """Responses API (gpt-5.2-pro, etc.)."""
        max_retries = 6
        for attempt in range(max_retries):
            try:
                response = await self.client.responses.create(
                    model=model,
                    instructions=system_prompt,
                    input=user_prompt,
                    max_output_tokens=max_completion_tokens,
                )
                return response.output_text
            except (openai.RateLimitError, openai.APIStatusError) as e:
                if isinstance(e, openai.APIStatusError) and e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
        # Final attempt — let any exception propagate.
        response = await self.client.responses.create(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            max_output_tokens=max_completion_tokens,
        )
        return response.output_text
