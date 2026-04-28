import json
from typing import Optional

from openai import APIStatusError, OpenAI

from core.providers import ProviderConfig, resolve_config


class LLMResponseError(Exception):
    def __init__(self, message: str, raw_response: Optional[str] = None):
        super().__init__(message)
        self.raw_response = raw_response


class RateLimitError(Exception):
    def __init__(self, model: str, message: str = ""):
        self.model = model
        super().__init__(f"Rate limit exceeded for model {model}: {message}")


class ModelQualityError(Exception):
    def __init__(self, model: str, message: str = ""):
        self.model = model
        super().__init__(f"Model {model} produced invalid output: {message}")


class LLMClient:
    MAX_JSON_RETRIES = 2

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        config_file: Optional[str] = None,
        config: Optional[ProviderConfig] = None,
    ):
        self._user_specified_model = model

        if config is not None:
            self.config = config
        else:
            self.config = resolve_config(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
                max_tokens=max_tokens,
                temperature=temperature,
                config_file=config_file,
            )

        self._fallback_models = list(self.config.fallback_models)
        if self._user_specified_model:
            self._fallback_models = []

        self._current_model_index = -1
        self._tried_models: list[str] = []

        client_kwargs = {"api_key": self.config.api_key}
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url

        self.client = OpenAI(**client_kwargs)

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def max_tokens(self) -> int:
        return self.config.max_tokens

    @property
    def temperature(self) -> float:
        return self.config.temperature

    @property
    def fallback_models(self) -> list[str]:
        return self._fallback_models

    def _switch_to_next_model(self, reason: str = "Rate limited") -> bool:
        if not self._fallback_models:
            return False

        next_index = self._current_model_index + 1
        if next_index >= len(self._fallback_models):
            return False

        next_model = self._fallback_models[next_index]
        old_model = self.config.model
        self.config.model = next_model
        self._current_model_index = next_index
        self._tried_models.append(old_model)
        print(f"[LLM] ⚠️  {reason} on {old_model}, switching to {next_model}")
        return True

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        while True:
            try:
                return self._chat_non_stream(
                    system_prompt, user_prompt, temperature, max_tokens
                )
            except RateLimitError:
                if not self._switch_to_next_model("Rate limited"):
                    raise
            except LLMResponseError:
                pass

            try:
                return self._chat_stream(
                    system_prompt, user_prompt, temperature, max_tokens
                )
            except RateLimitError:
                if not self._switch_to_next_model("Rate limited"):
                    raise

    def _check_rate_limit(self, error: Exception):
        if isinstance(error, APIStatusError):
            if error.status_code == 429:
                raise RateLimitError(self.model, str(error))
            if error.status_code == 403:
                raise RateLimitError(self.model, str(error))
            if error.status_code == 400:
                msg = str(error).lower()
                if any(kw in msg for kw in ["input length", "max_tokens", "context", "token limit", "too long", "too many"]):
                    raise RateLimitError(self.model, f"Input too long for model: {error}")

    def _chat_non_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=(
                    temperature if temperature is not None else self.temperature
                ),
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
            )
        except APIStatusError as e:
            self._check_rate_limit(e)
            raise LLMResponseError(
                f"LLM API error (status={e.status_code}): {e.message}. Model: {self.model}",
                raw_response=str(e),
            ) from e

        if not response.choices:
            raise LLMResponseError(
                f"LLM returned no choices in non-stream mode. Model: {self.model}",
                raw_response=str(response),
            )

        choice = response.choices[0]
        content = choice.message.content

        if content is None:
            finish_reason = choice.finish_reason
            raise LLMResponseError(
                f"LLM returned None content (finish_reason={finish_reason}). Model: {self.model}",
                raw_response=str(response),
            )

        return content

    def _chat_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=(
                    temperature if temperature is not None else self.temperature
                ),
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                stream=True,
            )
        except APIStatusError as e:
            self._check_rate_limit(e)
            raise LLMResponseError(
                f"LLM API error (status={e.status_code}): {e.message}. Model: {self.model}",
                raw_response=str(e),
            ) from e

        reasoning_parts: list[str] = []
        content_parts: list[str] = []

        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                reasoning_parts.append(delta.reasoning_content)
            if delta.content:
                content_parts.append(delta.content)

        if not content_parts and reasoning_parts:
            raise LLMResponseError(
                f"LLM only returned reasoning content without final answer. "
                f"Model: {self.model}. "
                f"Reasoning preview: {''.join(reasoning_parts)[:200]}",
                raw_response="".join(reasoning_parts),
            )

        if not content_parts:
            raise LLMResponseError(
                f"LLM returned no content in stream mode. Model: {self.model}",
            )

        return "".join(content_parts)

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> dict:
        retries = 0
        while True:
            content = self.chat(system_prompt, user_prompt, temperature, max_tokens)
            try:
                return self._parse_json(content)
            except LLMResponseError as e:
                retries += 1
                if retries <= self.MAX_JSON_RETRIES and self._switch_to_next_model(
                    "Invalid output"
                ):
                    continue
                raise

    def _parse_json(self, content: str) -> dict:
        original = content
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            preview = original[:500] if len(original) > 500 else original
            raise LLMResponseError(
                f"Failed to parse LLM response as JSON: {e}\n"
                f"Response preview:\n{preview}",
                raw_response=original,
            ) from e

        if not isinstance(result, dict):
            raise LLMResponseError(
                f"LLM response is not a JSON object, got {type(result).__name__}",
                raw_response=original,
            )

        return result

    def __repr__(self) -> str:
        return (
            f"LLMClient(provider={self.config.name}, "
            f"model={self.model}, "
            f"base_url={self.config.base_url or '(default)'})"
        )
