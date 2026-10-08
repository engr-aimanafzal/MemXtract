"""One interface for the free LLM APIs, with automatic fallback.

Order (editable with the LLM_ORDER secret): Gemini -> Groq -> OpenRouter.
A provider is used only if its key exists in Streamlit secrets.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import requests

from . import config

TIMEOUT = 90


class LLMError(Exception):
    pass


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


def configured_providers() -> list:
    order = [p.strip().lower() for p in config.secret("LLM_ORDER", "gemini,groq,openrouter").split(",") if p.strip()]
    keys = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
    return [p for p in order if p in keys and config.secret(keys[p])]


def _fail(provider: str, r: requests.Response):
    snippet = (r.text or "")[:200].replace("\n", " ")
    raise LLMError(f"{provider}: HTTP {r.status_code} {snippet}")


def _call_gemini(prompt, system, json_mode, temperature, max_tokens):
    model = config.secret("GEMINI_MODEL", "gemini-flash-latest")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"x-goog-api-key": config.secret("GEMINI_API_KEY"), "Content-Type": "application/json"}
    gen = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    if r.status_code != 200:
        _fail("gemini", r)
    cands = r.json().get("candidates") or []
    if not cands:
        raise LLMError("gemini: no candidates returned (possibly blocked)")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise LLMError("gemini: empty response")
    return text, model


def _call_openai_compat(provider, url, key, model, prompt, system, temperature, max_tokens):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["X-Title"] = "Paper RAG Agent"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    if r.status_code != 200:
        _fail(provider, r)
    try:
        text = r.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError):
        raise LLMError(f"{provider}: unexpected response format")
    if not text.strip():
        raise LLMError(f"{provider}: empty response")
    return text, model


def call_llm(prompt, system="", json_mode=False, temperature=0.1, max_tokens=4096, providers=None) -> LLMResult:
    providers = providers or configured_providers()
    if not providers:
        raise LLMError(
            "No LLM API key found. Add GEMINI_API_KEY (and optionally GROQ_API_KEY / OPENROUTER_API_KEY) "
            "in Streamlit -> App settings -> Secrets."
        )
    errors = []
    for p in providers:
        try:
            if p == "gemini":
                text, model = _call_gemini(prompt, system, json_mode, temperature, max_tokens)
            elif p == "groq":
                model = config.secret("GROQ_MODEL", "openai/gpt-oss-120b")
                text, model = _call_openai_compat(
                    "groq", "https://api.groq.com/openai/v1/chat/completions",
                    config.secret("GROQ_API_KEY"), model, prompt, system, temperature, max_tokens)
            elif p == "openrouter":
                model = config.secret("OPENROUTER_MODEL", "openrouter/free")
                text, model = _call_openai_compat(
                    "openrouter", "https://openrouter.ai/api/v1/chat/completions",
                    config.secret("OPENROUTER_API_KEY"), model, prompt, system, temperature, max_tokens)
            else:
                continue
            return LLMResult(text=text, provider=p, model=model)
        except (LLMError, requests.RequestException) as e:
            errors.append(str(e)[:250])
    hint = ""
    if any("429" in e for e in errors):
        hint = " (a free-tier rate limit was hit - wait a minute and try again)"
    raise LLMError("All LLM providers failed" + hint + ": " + " | ".join(errors))


def extract_json(text: str):
    """Parse JSON from an LLM reply, tolerating code fences and surrounding prose."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if not starts:
        raise LLMError("The model did not return JSON")
    start = min(starts)
    end = max(t.rfind("}"), t.rfind("]"))
    if end <= start:
        raise LLMError("The model returned incomplete JSON")
    try:
        return json.loads(t[start:end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"Could not parse the model's JSON ({e.msg})")
