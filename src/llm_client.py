#!/usr/bin/env python3
"""
LLM client — Gemini 2.0 Flash (free tier) → Groq llama3 fallback.
Both are completely free with API keys.

Get keys:
  Gemini : https://aistudio.google.com/app/apikey   (free, generous limits)
  Groq   : https://console.groq.com/keys             (free tier, fast)
"""

import json
import logging
import os
import time
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

GEMINI_KEY  = os.environ.get("GEMINI_KEY", "")
GROQ_KEY    = os.environ.get("GROQ_API_KEY", "")

GEMINI_MODEL = "gemini-2.0-flash"
GROQ_MODEL   = "llama-3.3-70b-versatile"
MAX_RETRIES  = 3


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 60) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _call_gemini(prompt: str, max_tokens: int) -> str:
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_KEY not set")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.85},
    }
    data = _post_json(url, payload, {"Content-Type": "application/json"})
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_groq(prompt: str, max_tokens: int) -> str:
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.85,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_KEY}",
    }
    data = _post_json(url, payload, headers)
    return data["choices"][0]["message"]["content"]


def generate_text(prompt: str, max_tokens: int = 2048) -> str:
    """Try Gemini first, fall back to Groq. Raises if both fail."""
    providers = [("gemini", _call_gemini), ("groq", _call_groq)]
    errors = []

    for name, fn in providers:
        for attempt in range(MAX_RETRIES):
            try:
                result = fn(prompt, max_tokens)
                log.info(f"LLM response via {name}")
                return result
            except Exception as e:
                log.warning(f"{name} attempt {attempt+1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        errors.append(name)

    raise RuntimeError(f"All LLM providers failed: {errors}")
