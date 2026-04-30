import asyncio
import os
from google import genai
from google.genai import types
from inference.providers import Provider


class GoogleProvider(Provider):
    """Google Gemini provider with exponential-backoff retry."""

    def __init__(self, api_key: str = None, **kwargs):
        api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("No API key provided. Set GEMINI_API_KEY env var or pass --api_key.")
        self.client = genai.Client(api_key=api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "gemini-3-pro-preview",
        temperature: float = 0,
        max_completion_tokens: int = 32768,
        **kwargs,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_completion_tokens,
        )
        max_retries = 6
        for attempt in range(max_retries):
            try:
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=config,
                )
                return response.text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "500" in err_str or "503" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = 2 ** attempt
                    print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                    await asyncio.sleep(wait)
                else:
                    raise
        # Final attempt — let any exception propagate.
        response = await self.client.aio.models.generate_content(
            model=model,
            contents=user_prompt,
            config=config,
        )
        return response.text

    async def generate_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "gemini-3-pro-preview",
        temperature: float = 0,
        max_completion_tokens: int = 32768,
        **kwargs,
    ) -> dict:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_completion_tokens,
        )
        max_retries = 6
        for attempt in range(max_retries):
            try:
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=config,
                )
                return _gemini_response_to_meta(response)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "500" in err_str or "503" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = 2 ** attempt
                    print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                    await asyncio.sleep(wait)
                else:
                    raise
        response = await self.client.aio.models.generate_content(
            model=model,
            contents=user_prompt,
            config=config,
        )
        return _gemini_response_to_meta(response)


def _gemini_response_to_meta(response) -> dict:
    """Extract metadata from a google-genai GenerateContentResponse."""
    text = response.text or ""
    usage = getattr(response, "usage_metadata", None)
    completion_tokens = getattr(usage, "candidates_token_count", None) if usage else None
    prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    finish_reason = None
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        raw = getattr(candidates[0], "finish_reason", None)
        # Gemini finish_reason is an enum; convert to its name string.
        name = getattr(raw, "name", None) or (str(raw) if raw is not None else None)
        if name:
            n = name.upper()
            if n == "STOP":
                finish_reason = "stop"
            elif n in ("MAX_TOKENS", "LENGTH"):
                finish_reason = "length"
            else:
                finish_reason = name.lower()
    return {
        "text": text,
        "completion_tokens": completion_tokens,
        "prompt_tokens": prompt_tokens,
        "finish_reason": finish_reason,
    }
