import asyncio
import openai
from inference.providers import Provider


class VLLMProvider(Provider):
    """Provider for a locally-running vLLM OpenAI-compatible server.

    Connects to http://localhost:{port}/v1 using the OpenAI client.

    Supports both instruction-tuned models (chat completions endpoint, with
    chat templates) and base models (completions endpoint, raw autocomplete).

    Base models are auto-detected: if the chat completions endpoint returns
    "default chat template is no longer allowed", the provider permanently
    switches to the /v1/completions endpoint for that model and concatenates
    system + user prompts as raw text. Set `base_model=True` at construction
    time to skip the auto-detection.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "local",
        base_model: bool = False,
        **kwargs,
    ):
        self.client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._base_model: dict[str, bool] = {}
        self._force_base_model = base_model

    @staticmethod
    def _is_chat_template_error(err: openai.APIStatusError) -> bool:
        msg = str(getattr(err, "message", "") or err).lower()
        return "chat template" in msg

    @staticmethod
    def _build_raw_prompt(system_prompt: str, user_prompt: str) -> str:
        print(f"{system_prompt}\n\n{user_prompt}")
        if system_prompt:
            return f"{system_prompt}\n\n{user_prompt}"
        return user_prompt

    async def _completions(self, prompt: str, *, model, temperature, max_tokens, stop=None) -> str:
        """Call the legacy /v1/completions endpoint (no chat template)."""
        kwargs = {}
        if stop:
            kwargs["stop"] = stop
        response = await self.client.completions.create(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].text or ""

    async def _chat(self, system_prompt, user_prompt, *, model, temperature, max_tokens, stop=None) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        kwargs = {}
        if stop:
            kwargs["stop"] = stop
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            **kwargs,
        )
        choice = response.choices[0].message
        content = choice.content or ""
        # Qwen3.5 with --reasoning-parser qwen3: thinking tokens are returned
        # in reasoning_content, stripped from content. Prepend them so the
        # full trace is stored and the grader still sees the final \boxed{}.
        reasoning = getattr(choice, "reasoning_content", None) or getattr(choice, "reasoning", None)
        if reasoning:
            return f"<think>\n{reasoning}\n</think>\n{content}"
        return content

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str,
        temperature: float = 0,
        max_completion_tokens: int = 32768,
        stop: list[str] | None = None,
        **kwargs,
    ) -> str:
        is_base = self._force_base_model or self._base_model.get(model, False)
        max_retries = 6

        for attempt in range(max_retries):
            try:
                if is_base:
                    return await self._completions(
                        self._build_raw_prompt(system_prompt, user_prompt),
                        model=model, temperature=temperature, max_tokens=max_completion_tokens, stop=stop,
                    )
                return await self._chat(
                    system_prompt, user_prompt,
                    model=model, temperature=temperature, max_tokens=max_completion_tokens, stop=stop,
                )
            except openai.BadRequestError as e:
                if not is_base and self._is_chat_template_error(e):
                    print(f"[vllm] '{model}' has no chat template — switching to /v1/completions (base-model mode)")
                    self._base_model[model] = True
                    is_base = True
                    continue
                raise
            except (openai.RateLimitError, openai.APIStatusError) as e:
                if isinstance(e, openai.APIStatusError) and e.status_code < 500 and e.status_code != 429:
                    raise
                wait = 2 ** attempt
                print(f"[retry {attempt+1}/{max_retries}] {e} — waiting {wait}s")
                await asyncio.sleep(wait)

        # Final attempt — let any exception propagate.
        if is_base:
            return await self._completions(
                self._build_raw_prompt(system_prompt, user_prompt),
                model=model, temperature=temperature, max_tokens=max_completion_tokens, stop=stop,
            )
        return await self._chat(
            system_prompt, user_prompt,
            model=model, temperature=temperature, max_tokens=max_completion_tokens, stop=stop,
        )
