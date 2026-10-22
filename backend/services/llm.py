"""Small Groq client that always returns parsed JSON (or a clear error)."""
import json
import logging
import re

import requests

import config

log = logging.getLogger(__name__)

_session = requests.Session()


class LLMError(Exception):
    def __init__(self, message: str, status: int = 0, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


def _parse_json(content: str):
    if not content:
        return None
    try:
        data = json.loads(content)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", content, re.S)  # JSON wrapped in ```json fences or extra text
    if m:
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def chat_json(system: str, user: str, model: str, reasoning_effort: str = "medium",
              max_tokens: int = 2048, timeout: int = 45) -> dict:
    if not config.GROQ_API_KEY:
        raise LLMError("The AI service isn't configured on this server (GROQ_API_KEY is missing).")

    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"}
    base = {
        "model": model,
        "temperature": 0.1,
        "max_completion_tokens": max_tokens,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if model.startswith("openai/gpt-oss"):
        base["reasoning_effort"] = reasoning_effort

    last = LLMError("The AI did not return a valid answer.", retryable=True)
    for json_mode in (True, False):  # retry once without JSON mode if Groq rejects the output
        payload = dict(base)
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            r = _session.post(config.GROQ_URL, headers=headers, json=payload, timeout=timeout)
        except requests.Timeout:
            raise LLMError("The AI took too long to respond. Please try again.", retryable=True)
        except requests.RequestException as exc:
            raise LLMError(f"Couldn't reach the AI service ({exc.__class__.__name__}).", retryable=True)

        if r.status_code != 200:
            try:
                err = r.json().get("error", {}) or {}
            except ValueError:
                err = {}
            code = err.get("code", "")
            log.warning("Groq %s error %s: %s", model, r.status_code, err.get("message", r.text[:200]))
            if code == "json_validate_failed" and json_mode:
                continue
            if r.status_code == 401:
                raise LLMError("The server's AI key is invalid. (Admin: update GROQ_API_KEY.)", 401)
            if r.status_code == 429:
                raise LLMError("The AI service is busy right now. Please try again in a minute.", 429, True)
            if r.status_code == 404 or code == "model_not_found":
                raise LLMError(f"AI model '{model}' isn't available. (Admin: change GROQ_MODEL.)", 404, True)
            if r.status_code >= 500:
                raise LLMError("The AI service had a temporary problem. Please try again.", r.status_code, True)
            raise LLMError(f"The AI service rejected the request ({r.status_code}).", r.status_code)

        try:
            content = r.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            last = LLMError("Unexpected response from the AI service.", retryable=True)
            continue
        parsed = _parse_json(content)
        if parsed is not None:
            return parsed
        last = LLMError("The AI did not return a valid answer.", retryable=True)
    raise last
