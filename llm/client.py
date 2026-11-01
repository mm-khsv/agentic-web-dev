"""Cloudflare Workers AI client using Python standard library only."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _load_dotenv():
    """Load simple KEY=VALUE settings from the repository .env file."""
    dotenv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env",
    )
    if not os.path.isfile(dotenv_path):
        return
    with open(dotenv_path, "r", encoding="utf-8-sig") as dotenv_file:
        for raw_line in dotenv_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

DEFAULT_MODEL = "@cf/google/gemma-4-26b-a4b-it"


class LLMClient:
    """Generate text using Cloudflare Workers AI."""

    def __init__(self):
        self.account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        self.api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
        self.model = os.environ.get("CLOUDFLARE_MODEL", DEFAULT_MODEL).strip()
        self.timeout = int(os.environ.get("CLOUDFLARE_TIMEOUT", "120"))
        self.max_tokens = int(os.environ.get("CLOUDFLARE_MAX_TOKENS", "2500"))

        if not self.account_id or not self.api_token:
            raise ValueError(
                "Cloudflare requires CLOUDFLARE_ACCOUNT_ID and "
                "CLOUDFLARE_API_TOKEN environment variables."
            )
        if not self.model:
            raise ValueError("CLOUDFLARE_MODEL cannot be empty.")
        if self.max_tokens < 1:
            raise ValueError("CLOUDFLARE_MAX_TOKENS must be positive.")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            + self.account_id
            + "/ai/run/"
            + self.model
        )

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "chat_template_kwargs": {"enable_thinking": False},
            "max_tokens": self.max_tokens,
            "temperature": 0.2,
        }

        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.api_token,
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            # Do not include request headers or the API token in error output.
            try:
                detail = exc.read().decode("utf-8", errors="replace")
                data = json.loads(detail)
                errors = data.get("errors", [])
                message = "; ".join(
                    str(item.get("message", "Cloudflare API error"))
                    for item in errors
                    if isinstance(item, dict)
                )
            except Exception:
                message = "Cloudflare returned an HTTP error."
            raise RuntimeError(
                "Cloudflare request failed (HTTP "
                + str(exc.code)
                + "): "
                + (message or "API request rejected.")
            ) from None
        except URLError as exc:
            raise RuntimeError(
                "Could not reach Cloudflare Workers AI: "
                + str(getattr(exc, "reason", "network error"))
            ) from None
        except TimeoutError:
            raise RuntimeError("Cloudflare request timed out.") from None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError("Cloudflare returned invalid JSON.") from None

        if data.get("success") is False:
            errors = data.get("errors", [])
            messages = [
                str(item.get("message", "Cloudflare API error"))
                for item in errors
                if isinstance(item, dict)
            ]
            raise RuntimeError(
                "Cloudflare API reported failure: "
                + ("; ".join(messages) or "unspecified API error")
            )

        result = data.get("result") or {}
        if not isinstance(result, dict):
            raise RuntimeError("Cloudflare returned an invalid result structure.")

        choices = result.get("choices") or []
        first_choice = (
            choices[0]
            if isinstance(choices, list)
            and choices
            and isinstance(choices[0], dict)
            else {}
        )

        finish_reason = (
            result.get("finish_reason")
            or result.get("stop_reason")
            or first_choice.get("finish_reason")
            or first_choice.get("stop_reason")
        )

        normalized_reason = (
            str(finish_reason).strip().lower()
            if finish_reason is not None
            else ""
        )

        if normalized_reason in {
            "length",
            "max_tokens",
            "max_output_tokens",
            "token_limit",
            "max_completion_tokens",
        }:
            raise RuntimeError(
                "Cloudflare output was truncated at the configured token limit "
                f"({self.max_tokens}). Increase the artifact-specific token budget."
            )

        text = result.get("response")

        # Support the OpenAI-compatible response shape too.
        if not isinstance(text, str) or not text.strip():
            if first_choice:
                message = first_choice.get("message") or {}
                text = message.get("content")

        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(
                "Cloudflare returned no text. Check the model response "
                "and token limit; reasoning-only output is not accepted."
            )

        return text.strip()


class PollinationsClient:
    """Generate text through the Pollinations OpenAI-compatible API."""

    def __init__(self):
        self.api_key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
        self.model = os.environ.get(
            "POLLINATIONS_MODEL", "openai/gpt-oss-20b"
        ).strip()
        self.timeout = int(os.environ.get("POLLINATIONS_TIMEOUT", "180"))
        self.max_tokens = int(
            os.environ.get("POLLINATIONS_MAX_TOKENS", "3500")
        )

        if not self.api_key:
            raise ValueError(
                "Pollinations requires POLLINATIONS_API_KEY."
            )
        if not self.model:
            raise ValueError("POLLINATIONS_MODEL cannot be empty.")
        if self.max_tokens < 1:
            raise ValueError("POLLINATIONS_MAX_TOKENS must be positive.")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = "https://gen.pollinations.ai/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.2,
        }
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
                data = json.loads(detail)
                error = data.get("error", {})
                if isinstance(error, dict):
                    message = str(error.get("message", "API request rejected."))
                else:
                    message = str(error or "API request rejected.")
            except Exception:
                message = "Pollinations returned an HTTP error."
            raise RuntimeError(
                "Pollinations request failed (HTTP "
                + str(exc.code) + "): " + message
            ) from None
        except URLError as exc:
            raise RuntimeError(
                "Could not reach Pollinations: "
                + str(getattr(exc, "reason", "network error"))
            ) from None
        except TimeoutError:
            raise RuntimeError("Pollinations request timed out.") from None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError("Pollinations returned invalid JSON.") from None

        if not isinstance(data, dict):
            raise RuntimeError("Pollinations returned an invalid response.")

        if data.get("error"):
            error = data["error"]
            message = (
                error.get("message", "API request rejected.")
                if isinstance(error, dict) else str(error)
            )
            raise RuntimeError("Pollinations API error: " + str(message))

        choices = data.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            raise RuntimeError("Pollinations returned no completion choices.")

        choice = choices[0]
        finish_reason = str(choice.get("finish_reason") or "").strip().lower()
        if finish_reason in {
            "length", "max_tokens", "max_output_tokens",
            "token_limit", "max_completion_tokens",
        }:
            raise RuntimeError(
                "Pollinations output was truncated at the configured token "
                f"limit ({self.max_tokens}). Increase the artifact token budget."
            )

        message = choice.get("message") or {}
        text = message.get("content") if isinstance(message, dict) else None
        if isinstance(text, list):
            text = "".join(
                part.get("text", "") for part in text
                if isinstance(part, dict)
            )
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(
                "Pollinations returned no text. Reasoning-only output "
                "is not accepted."
            )
        return text.strip()
