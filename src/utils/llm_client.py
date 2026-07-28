"""Provider-agnostic LLM client with fallback routing.

Reads active provider and API keys from config/providers.json and the
environment. Replaces direct google-genai usage across the pipeline.
"""

import os
import re
import json
import time
from typing import Any

from .config_loader import load_providers, get_env_key_name, get_active_provider_config


class LLMError(Exception):
    """Raised when all providers/models fail."""
    pass


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```html"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _extract_json(text: str) -> Any:
    """Best-effort JSON extraction from a model response."""
    cleaned = _strip_code_fences(text)
    # Sometimes the model returns text around the JSON; try to find the first {...}
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise ValueError("No valid JSON found in model response")


# ── Provider implementations ─────────────────────────────────────────────────

def _call_gemini(prompt: str, provider_cfg: dict, api_key: str, temperature: float) -> str:
    try:
        from google import genai
    except ImportError as e:
        raise ImportError("google-genai is required for Gemini provider") from e

    client = genai.Client(api_key=api_key)
    models = provider_cfg.get("models", [])
    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"temperature": temperature} if temperature is not None else None,
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "503" in err or "UNAVAILABLE" in err:
                print(f"  ⚠️ Gemini {model_name} rate limited/unavailable. Switching...")
                continue
            print(f"  ⚠️ Gemini {model_name} error: {err[:120]}")
            continue
    raise LLMError("Gemini limits exhausted across all configured models.")


def _call_openai(prompt: str, provider_cfg: dict, api_key: str, temperature: float) -> str:
    try:
        import openai
    except ImportError as e:
        raise ImportError("openai package is required for OpenAI provider") from e

    client = openai.OpenAI(api_key=api_key)
    models = provider_cfg.get("models", ["gpt-4o-mini"])
    for model_name in models:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature if temperature is not None else 0.2,
            )
            if response and response.choices:
                return response.choices[0].message.content or ""
        except Exception as e:
            err = str(e)
            if "429" in err or "503" in err or "overloaded" in err.lower():
                print(f"  ⚠️ OpenAI {model_name} rate limited/unavailable. Switching...")
                continue
            print(f"  ⚠️ OpenAI {model_name} error: {err[:120]}")
            continue
    raise LLMError("OpenAI limits exhausted across all configured models.")


def _call_anthropic(prompt: str, provider_cfg: dict, api_key: str, temperature: float) -> str:
    try:
        import anthropic
    except ImportError as e:
        raise ImportError("anthropic package is required for Anthropic provider") from e

    client = anthropic.Anthropic(api_key=api_key)
    models = provider_cfg.get("models", ["claude-3-5-haiku-latest"])
    for model_name in models:
        try:
            response = client.messages.create(
                model=model_name,
                max_tokens=4096,
                temperature=temperature if temperature is not None else 0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            if response and response.content:
                # Anthropic content is a list of TextBlock objects
                parts = [block.text for block in response.content if hasattr(block, "text")]
                return "\n".join(parts)
        except Exception as e:
            err = str(e)
            if "429" in err or "503" in err or "overloaded" in err.lower():
                print(f"  ⚠️ Anthropic {model_name} rate limited/unavailable. Switching...")
                continue
            print(f"  ⚠️ Anthropic {model_name} error: {err[:120]}")
            continue
    raise LLMError("Anthropic limits exhausted across all configured models.")


def _call_local(prompt: str, provider_cfg: dict, api_key: str, temperature: float) -> str:
    try:
        import openai
    except ImportError as e:
        raise ImportError("openai package is required for local/Ollama provider") from e

    base_url = provider_cfg.get("base_url", "http://localhost:11434/v1")
    models = provider_cfg.get("models", ["llama3.2"])
    client = openai.OpenAI(base_url=base_url, api_key=api_key or "not-needed")
    for model_name in models:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature if temperature is not None else 0.2,
            )
            if response and response.choices:
                return response.choices[0].message.content or ""
        except Exception as e:
            print(f"  ⚠️ Local {model_name} error: {str(e)[:120]}")
            continue
    raise LLMError("Local LLM not reachable or failed for all configured models.")


_DISPATCH = {
    "gemini": _call_gemini,
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "local": _call_local,
}


# ── Public API ───────────────────────────────────────────────────────────────

def generate_text(prompt: str, temperature: float | None = 0.2) -> str:
    """Generate text using the configured active provider.

    Args:
        prompt: The full prompt to send.
        temperature: Sampling temperature (provider-dependent).

    Returns:
        Raw text response from the model.

    Raises:
        LLMError: If the active provider is unavailable or all models fail.
    """
    providers = load_providers()
    active = providers.get("active_provider", "gemini")
    provider_cfg = providers.get("providers", {}).get(active)
    if not provider_cfg or not provider_cfg.get("enabled"):
        raise LLMError(f"Provider '{active}' is not enabled or not configured.")

    env_key = provider_cfg.get("api_key_env", f"{active.upper()}_API_KEY")
    api_key = os.getenv(env_key, "").strip()
    if not api_key and active != "local":
        raise LLMError(f"No API key found for provider '{active}' (env: {env_key}).")

    caller = _DISPATCH.get(active)
    if not caller:
        raise LLMError(f"Unknown provider '{active}'.")

    return caller(prompt, provider_cfg, api_key, temperature)


def generate_json(prompt: str, temperature: float | None = 0.2) -> Any:
    """Generate and parse JSON from the configured provider."""
    text = generate_text(prompt, temperature=temperature)
    return _extract_json(text)


def get_batch_delay_seconds() -> int:
    """Return configured delay between batches (defaults to 15s for Gemini)."""
    cfg = get_active_provider_config()
    return int(cfg.get("delay_between_batches_seconds", 15))


if __name__ == "__main__":
    # Quick sanity check with a trivial prompt
    try:
        print(generate_text("Say hello in one word."))
    except Exception as e:
        print(f"LLM not available: {e}")
