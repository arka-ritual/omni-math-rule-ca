import asyncio
import openai
from inference.providers import Provider


class VLLMProvider(Provider):
    """Provider for a locally-running vLLM OpenAI-compatible server.

    Connects to http://localhost:{port}/v1 using the OpenAI client.
    Works with any model served via `vllm serve`, including Qwen3.5 which
    returns reasoning_content separately when --reasoning-parser qwen3 is used.
    """

    def __init__(self, base_url: str = "http://localhost:8000/v1", api_key: str = "local", **kwargs):
        self.client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str,
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
                choice = response.choices[0].message
                content = choice.content or ""

                # Qwen3.5 with --reasoning-parser qwen3: thinking tokens are
                # returned in reasoning_content, stripped from content. Prepend
                # them so the full trace is stored and the grader still sees the
                # final \boxed{} in content.
                reasoning = getattr(choice, "reasoning", None)
                if reasoning:
                    return f"<think>\n{reasoning}\n</think>\n{content}"
                return content
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
        choice = response.choices[0].message
        content = choice.content or ""
        reasoning = getattr(choice, "reasoning", None)
        if reasoning:
            return f"<think>\n{reasoning}\n</think>\n{content}"
        return content
