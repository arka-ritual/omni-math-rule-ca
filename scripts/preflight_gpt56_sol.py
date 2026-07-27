#!/usr/bin/env python3
"""Fail closed if OpenRouter's current GPT-5.6 Sol listing is unexpected."""

from __future__ import annotations

import json
from urllib.request import urlopen


MODEL = "openai/gpt-5.6-sol"
ENDPOINTS_URL = f"https://openrouter.ai/api/v1/models/{MODEL}/endpoints"


def validate_listing(payload: dict) -> dict:
    data = payload.get("data") or {}
    if data.get("id") != MODEL:
        raise ValueError(f"OpenRouter returned model {data.get('id')!r}, expected {MODEL!r}")

    endpoints = data.get("endpoints") or []
    standard = next((endpoint for endpoint in endpoints if endpoint.get("tag") == "openai"), None)
    if standard is None:
        raise ValueError("OpenRouter does not list the standard `openai` endpoint")
    if standard.get("provider_name") != "OpenAI":
        raise ValueError(
            f"`openai` endpoint is hosted by {standard.get('provider_name')!r}, expected 'OpenAI'"
        )
    if standard.get("status") != 0:
        raise ValueError(f"standard OpenAI endpoint is unavailable (status={standard.get('status')})")
    if (standard.get("max_completion_tokens") or 0) < 64_000:
        raise ValueError("standard OpenAI endpoint cannot provide the requested 64k output budget")

    supported = set(standard.get("supported_parameters") or [])
    missing = {"reasoning", "max_tokens"} - supported
    if missing:
        raise ValueError(f"standard OpenAI endpoint is missing parameters: {sorted(missing)}")
    return standard


def main() -> None:
    with urlopen(ENDPOINTS_URL, timeout=30) as response:
        payload = json.load(response)
    endpoint = validate_listing(payload)
    pricing = endpoint.get("pricing") or {}
    prompt_per_million = float(pricing["prompt"]) * 1_000_000
    completion_per_million = float(pricing["completion"]) * 1_000_000
    print(
        "OpenRouter preflight passed: "
        f"model={MODEL}, provider_tag=openai, provider=OpenAI, "
        f"upstream_model={endpoint.get('name')}, "
        f"price=${prompt_per_million:g}/M input + ${completion_per_million:g}/M output"
    )


if __name__ == "__main__":
    main()
