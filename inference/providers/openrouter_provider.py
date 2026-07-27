import asyncio
import copy
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
            default_headers={"X-OpenRouter-Metadata": "enabled"},
        )
        # Optional OpenRouter sub-provider routing (e.g. force "DeepSeek" for
        # deepseek/* models). When set, OpenRouter routes only to that
        # upstream, does not silently fall back to a different host, and
        # requires the selected endpoint to support every request parameter.
        # See https://openrouter.ai/docs/guides/routing/provider-selection
        if openrouter_provider:
            self._extra_body = {
                "provider": {
                    "order": [openrouter_provider],
                    "allow_fallbacks": False,
                    "require_parameters": True,
                }
            }
        else:
            self._extra_body = None

    def _request_kwargs(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str,
        temperature: float | None,
        max_completion_tokens: int,
        reasoning_effort: str | None,
        stop: list[str] | None,
    ) -> dict:
        """Build one OpenRouter Chat Completions request.

        OpenRouter's normalized API uses ``max_tokens``. Reasoning is sent in
        OpenRouter's documented nested shape, while ``temperature=None`` means
        omit the field entirely and preserve the model/provider default.
        """
        create_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_completion_tokens,
        }
        if temperature is not None:
            create_kwargs["temperature"] = temperature
        if stop:
            create_kwargs["stop"] = stop

        extra_body = copy.deepcopy(self._extra_body) if self._extra_body else {}
        if reasoning_effort:
            extra_body["reasoning"] = {"effort": reasoning_effort}
        if extra_body:
            create_kwargs["extra_body"] = extra_body
        return create_kwargs

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "anthropic/claude-opus-4-6",
        temperature: float | None = 0,
        max_completion_tokens: int = 32768,
        reasoning_effort: str | None = None,
        stop: list[str] | None = None,
        **kwargs,
    ) -> str:
        meta = await self.generate_with_meta(
            system_prompt,
            user_prompt,
            model=model,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            reasoning_effort=reasoning_effort,
            stop=stop,
        )
        return meta["text"]

    async def generate_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str = "anthropic/claude-opus-4-6",
        temperature: float | None = 0,
        max_completion_tokens: int = 32768,
        reasoning_effort: str | None = None,
        stop: list[str] | None = None,
        **kwargs,
    ) -> dict:
        create_kwargs = self._request_kwargs(
            system_prompt,
            user_prompt,
            model=model,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
            reasoning_effort=reasoning_effort,
            stop=stop,
        )
        max_retries = 6
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(**create_kwargs)
                return _openrouter_response_to_meta(response)
            except (openai.RateLimitError, openai.APIStatusError) as e:
                if isinstance(e, openai.APIStatusError) and e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)
        response = await self.client.chat.completions.create(**create_kwargs)
        return _openrouter_response_to_meta(response)


def _as_dict(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {}


def _selected_endpoint(metadata: dict) -> dict:
    endpoints = _as_dict(metadata.get("endpoints"))
    for endpoint in endpoints.get("available", []) or []:
        endpoint = _as_dict(endpoint)
        if endpoint.get("selected"):
            return endpoint
    return {}


def _provider_name(response_data: dict, metadata: dict) -> str | None:
    provider = response_data.get("provider") or metadata.get("provider")
    if isinstance(provider, dict):
        provider = provider.get("name") or provider.get("slug") or provider.get("tag")
    if provider:
        return str(provider)

    endpoint = _selected_endpoint(metadata)
    provider = (
        endpoint.get("provider_name")
        or endpoint.get("provider")
        or endpoint.get("tag")
    )
    return str(provider) if provider else None


def _openrouter_response_to_meta(response) -> dict:
    """Extract text, token accounting, cost, and selected route.

    Extra OpenRouter response fields are retained by the OpenAI SDK as
    Pydantic extras, so ``model_dump`` is the most reliable way to access
    them without coupling this provider to a particular SDK release.
    """
    result = _chat_response_to_meta(response)
    response_data = _as_dict(response)
    usage = _as_dict(response_data.get("usage"))
    completion_details = _as_dict(usage.get("completion_tokens_details"))
    prompt_details = _as_dict(usage.get("prompt_tokens_details"))
    cost_details = _as_dict(usage.get("cost_details"))
    metadata = _as_dict(response_data.get("openrouter_metadata"))

    result.update({
        "total_tokens": usage.get("total_tokens"),
        "reasoning_tokens": completion_details.get("reasoning_tokens"),
        "cached_tokens": prompt_details.get("cached_tokens"),
        "cache_write_tokens": prompt_details.get("cache_write_tokens"),
        "cost": usage.get("cost"),
        "upstream_inference_cost": cost_details.get("upstream_inference_cost"),
        "response_id": response_data.get("id"),
        "response_model": response_data.get("model"),
        "openrouter_requested_model": metadata.get("requested"),
        "openrouter_provider": _provider_name(response_data, metadata),
        "openrouter_attempt": metadata.get("attempt"),
        "openrouter_route_strategy": metadata.get("strategy"),
        "openrouter_region": metadata.get("region"),
        "openrouter_route_summary": metadata.get("summary"),
        "openrouter_is_byok": metadata.get("is_byok"),
    })
    return result
