import asyncio
import openai
from inference.providers import Provider

# Models that require the Responses API instead of Chat Completions.
RESPONSES_API_MODELS = {"gpt-5.2-pro", "gpt-5.2-codex"}


def _normalize_finish_reason(raw: str | None) -> str | None:
    """Normalize OpenAI/OpenAI-compatible finish_reason strings.

    OpenAI returns: "stop", "length", "content_filter", "tool_calls",
    "function_call". We collapse anything that isn't a max-token
    truncation to its raw value (the evaluator only treats "length"
    specially).
    """
    return raw


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

    # ----- generate_with_meta (used by intervention runner) -----

    async def generate_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "gpt-5.2",
        temperature: float = 0,
        max_completion_tokens: int = 32768,
        **kwargs,
    ) -> dict:
        if model in RESPONSES_API_MODELS:
            return await self._generate_responses_with_meta(
                system_prompt, user_prompt,
                model=model, temperature=temperature,
                max_completion_tokens=max_completion_tokens,
            )
        return await self._generate_chat_with_meta(
            system_prompt, user_prompt,
            model=model, temperature=temperature,
            max_completion_tokens=max_completion_tokens,
        )

    async def _generate_chat_with_meta(
        self, system_prompt, user_prompt, *, model, temperature, max_completion_tokens,
    ) -> dict:
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
                return _chat_response_to_meta(response)
            except (openai.RateLimitError, openai.APIStatusError) as e:
                if isinstance(e, openai.APIStatusError) and e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
        )
        return _chat_response_to_meta(response)

    async def _generate_responses_with_meta(
        self, system_prompt, user_prompt, *, model, temperature, max_completion_tokens,
    ) -> dict:
        max_retries = 6
        for attempt in range(max_retries):
            try:
                response = await self.client.responses.create(
                    model=model,
                    instructions=system_prompt,
                    input=user_prompt,
                    max_output_tokens=max_completion_tokens,
                )
                return _responses_to_meta(response)
            except (openai.RateLimitError, openai.APIStatusError) as e:
                if isinstance(e, openai.APIStatusError) and e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
        response = await self.client.responses.create(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            max_output_tokens=max_completion_tokens,
        )
        return _responses_to_meta(response)


def _chat_response_to_meta(response) -> dict:
    """Extract (text, completion_tokens, prompt_tokens, finish_reason) from
    an OpenAI/OpenAI-compatible chat completions response object."""
    choice = response.choices[0]
    msg = choice.message
    text = msg.content or ""
    reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
    if reasoning:
        text = f"<think>\n{reasoning}\n</think>\n{text}"
    usage = getattr(response, "usage", None)
    return {
        "text": text,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "finish_reason": _normalize_finish_reason(getattr(choice, "finish_reason", None)),
    }


def _responses_to_meta(response) -> dict:
    """Extract metadata from an OpenAI Responses API result."""
    text = getattr(response, "output_text", "") or ""
    usage = getattr(response, "usage", None)
    # Responses API: status="incomplete" and incomplete_details.reason="max_output_tokens"
    # signals truncation. Map to the chat-style "length".
    finish = "stop"
    incomplete = getattr(response, "incomplete_details", None)
    if incomplete is not None:
        reason = getattr(incomplete, "reason", None)
        if reason in ("max_output_tokens", "max_tokens"):
            finish = "length"
        elif reason:
            finish = str(reason)
    return {
        "text": text,
        "completion_tokens": getattr(usage, "output_tokens", None) if usage else None,
        "prompt_tokens": getattr(usage, "input_tokens", None) if usage else None,
        "finish_reason": finish,
    }
