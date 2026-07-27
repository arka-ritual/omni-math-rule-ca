import unittest
from types import SimpleNamespace
from unittest.mock import patch

from inference.inference_api import select_dataset
from inference.providers.openrouter_provider import (
    OpenRouterProvider,
    _openrouter_response_to_meta,
)
from scripts.preflight_gpt56_sol import validate_listing
from scripts.summarize_gpt56_sol import CELLS, expected_indices, validate_rows


class OpenRouterRequestTests(unittest.TestCase):
    @patch("inference.providers.openrouter_provider.openai.AsyncOpenAI")
    def test_request_pins_openai_and_explicit_high(self, async_openai):
        provider = OpenRouterProvider(api_key="test-key", openrouter_provider="openai")
        async_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            default_headers={"X-OpenRouter-Metadata": "enabled"},
        )

        request = provider._request_kwargs(
            "system",
            "user",
            model="openai/gpt-5.6-sol",
            temperature=None,
            max_completion_tokens=64_000,
            reasoning_effort="high",
            stop=None,
        )
        self.assertEqual(request["model"], "openai/gpt-5.6-sol")
        self.assertEqual(request["max_tokens"], 64_000)
        self.assertNotIn("temperature", request)
        self.assertEqual(request["extra_body"]["reasoning"], {"effort": "high"})
        self.assertEqual(
            request["extra_body"]["provider"],
            {
                "order": ["openai"],
                "allow_fallbacks": False,
                "require_parameters": True,
            },
        )

    def test_openrouter_metadata_and_cost_are_preserved(self):
        response_data = {
            "id": "gen-123",
            "model": "openai/gpt-5.6-sol-20260709",
            "provider": "OpenAI",
            "usage": {
                "prompt_tokens": 101,
                "completion_tokens": 202,
                "total_tokens": 303,
                "cost": 0.006565,
                "completion_tokens_details": {"reasoning_tokens": 180},
                "prompt_tokens_details": {"cached_tokens": 10},
                "cost_details": {"upstream_inference_cost": 0.005},
            },
            "openrouter_metadata": {"attempt": 1, "route_strategy": "manual"},
        }
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="answer", reasoning_content=None),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=101, completion_tokens=202),
            model_dump=lambda: response_data,
        )
        meta = _openrouter_response_to_meta(response)
        self.assertEqual(meta["text"], "answer")
        self.assertEqual(meta["cost"], 0.006565)
        self.assertEqual(meta["reasoning_tokens"], 180)
        self.assertEqual(meta["openrouter_provider"], "OpenAI")
        self.assertEqual(meta["response_model"], "openai/gpt-5.6-sol-20260709")


class SamplingTests(unittest.TestCase):
    def test_pilot_is_prefix_of_full_sample(self):
        dataset = [{"idx": i} for i in range(2821)]
        pilot = select_dataset(dataset, num_samples=5, start=0, seed=100)
        full = select_dataset(dataset, num_samples=100, start=0, seed=100)
        pilot_ids = {item["idx"] for item in pilot}
        full_ids = {item["idx"] for item in full}
        self.assertEqual(pilot_ids, {539, 903, 1464, 2279, 2637})
        self.assertTrue(pilot_ids < full_ids)
        self.assertEqual(pilot_ids, expected_indices(2821, 5))


class ValidationTests(unittest.TestCase):
    def test_model_listing_preflight_targets_standard_openai(self):
        endpoint = validate_listing({
            "data": {
                "id": "openai/gpt-5.6-sol",
                "endpoints": [{
                    "tag": "openai",
                    "provider_name": "OpenAI",
                    "status": 0,
                    "max_completion_tokens": 128_000,
                    "supported_parameters": ["reasoning", "max_tokens"],
                }],
            }
        })
        self.assertEqual(endpoint["tag"], "openai")

    def test_validator_rejects_wrong_upstream_provider(self):
        row = {
            "idx": 539,
            "request_provider": "openrouter",
            "request_model": "openai/gpt-5.6-sol",
            "request_openrouter_provider": "openai",
            "openrouter_provider": "Azure",
            "reasoning_effort": "high",
            "temperature": None,
            "max_completion_tokens": 64_000,
            "dataset_seed": 100,
            "response_model": "openai/gpt-5.6-sol-20260709",
            "cost": 0.01,
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300,
            "finish_reason": "stop",
        }
        with self.assertRaisesRegex(ValueError, "selected provider"):
            validate_rows(
                [row],
                cell=CELLS[0],
                expected_n=1,
                expected_ids={539},
            )


if __name__ == "__main__":
    unittest.main()
