import asyncio
import anthropic
from inference.providers import Provider


class AnthropicProvider(Provider):
    """Anthropic messages API provider with streaming and exponential-backoff retry."""

    def __init__(self, api_key: str = None, **kwargs):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)  # falls back to ANTHROPIC_API_KEY env var

    async def _stream_response(self, model, max_tokens, temperature, system, messages) -> str:
        """Stream a response and return the full text."""
        text = ""
        async with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        ) as stream:
            async for chunk in stream.text_stream:
                text += chunk
        return text

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "claude-opus-4-6",
        temperature: float = 0,
        max_completion_tokens: int = 32768,
        **kwargs,
    ) -> str:
        messages = [{"role": "user", "content": user_prompt}]
        max_retries = 6
        for attempt in range(max_retries):
            try:
                return await self._stream_response(
                    model=model,
                    max_tokens=max_completion_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=messages,
                )
            except anthropic.RateLimitError as e:
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
            except anthropic.APIStatusError as e:
                if e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
        # Final attempt — let any exception propagate.
        return await self._stream_response(
            model=model,
            max_tokens=max_completion_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )

    async def _stream_response_with_meta(
        self, model, max_tokens, temperature, system, messages
    ) -> dict:
        async with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        ) as stream:
            async for _ in stream.text_stream:
                pass
            final = await stream.get_final_message()
        text_parts = [
            block.text for block in final.content if getattr(block, "type", None) == "text"
        ]
        text = "".join(text_parts)
        # Anthropic stop_reason values: "end_turn", "max_tokens",
        # "stop_sequence", "tool_use", "pause_turn", "refusal".
        stop = getattr(final, "stop_reason", None)
        finish_reason = "length" if stop == "max_tokens" else (
            "stop" if stop in ("end_turn", "stop_sequence") else stop
        )
        usage = getattr(final, "usage", None)
        return {
            "text": text,
            "completion_tokens": getattr(usage, "output_tokens", None) if usage else None,
            "prompt_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "finish_reason": finish_reason,
        }

    async def generate_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "claude-opus-4-6",
        temperature: float = 0,
        max_completion_tokens: int = 32768,
        **kwargs,
    ) -> dict:
        messages = [{"role": "user", "content": user_prompt}]
        max_retries = 6
        for attempt in range(max_retries):
            try:
                return await self._stream_response_with_meta(
                    model=model,
                    max_tokens=max_completion_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=messages,
                )
            except anthropic.RateLimitError as e:
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
            except anthropic.APIStatusError as e:
                if e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
        return await self._stream_response_with_meta(
            model=model,
            max_tokens=max_completion_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )
