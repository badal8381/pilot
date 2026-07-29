from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import ClassVar

from pilot.integrations.llm.self_hosted import SelfHostedIntegration


class FrappeLLMIntegration(SelfHostedIntegration):
    """Frappe-hosted, OpenAI-compatible LLM at a fixed endpoint. Unlike the litellm
    providers there is no static catalog, so models are listed from the live
    `/models` endpoint and that call needs the user's API key."""

    # Keeping the IP hardcoded for now; will move to a domain once available.
    base_api: ClassVar[str] = "http://x.x.x.x/v1"
    requires_api_base: ClassVar[bool] = False
    free_text_model: ClassVar[bool] = False
    models_need_api_key: ClassVar[bool] = True

    @classmethod
    def providers(cls) -> dict[str, str]:
        return {"frappe-llm": "Frappe LLM"}

    @classmethod
    def get_models(cls, provider: str, api_key: str = "") -> list[str]:
        if not api_key:
            raise ValueError("Frappe LLM needs an API key to list models.")

        request = urllib.request.Request(
            url=f"{cls.base_api}/models",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ValueError("Frappe LLM rejected the API key.") from exc
            raise ValueError(f"Frappe LLM could not list models (HTTP {exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ValueError("Could not reach Frappe LLM to list models.") from exc
        except json.JSONDecodeError as exc:
            raise ValueError("Frappe LLM returned an unreadable model list.") from exc

        models = [model.get("id", "") for model in payload.get("data", [])]
        models = [model for model in models if model]
        if not models:
            raise ValueError("Frappe LLM returned no models for this API key.")
        return sorted(models)
