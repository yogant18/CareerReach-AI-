"""
AI providers a visitor can use with their own API key.

Groq runs through LangChain's ChatGroq. OpenAI (ChatGPT), Google Gemini and
Anthropic Claude are wrapped in a small LangChain Runnable so the prompt chains
in ``chains.py`` work the same way with every provider:

* OpenAI  -> official ``openai`` SDK
* Gemini  -> the same ``openai`` SDK pointed at Google's OpenAI-compatible endpoint
* Claude  -> official ``anthropic`` SDK
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

GROQ = "groq"
OPENAI = "openai"
GEMINI = "gemini"
ANTHROPIC = "anthropic"

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
REQUEST_TIMEOUT_SECONDS = 120.0

PROVIDERS: Dict[str, Dict[str, Any]] = {
    GROQ: {
        "label": "Groq (free)",
        "name": "Groq",
        "key_url": "https://console.groq.com/keys",
        "key_placeholder": "gsk_...",
        "key_hint": "Groq keys start with gsk_.",
        "cost_note": "Free, no card needed.",
        "default_models": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
        "guide": [
            "Open [console.groq.com/keys](https://console.groq.com/keys) and sign in.",
            "Click **Create API Key** and give it any name.",
            "Copy the key. It starts with `gsk_`.",
        ],
    },
    OPENAI: {
        "label": "OpenAI (ChatGPT)",
        "name": "OpenAI",
        "key_url": "https://platform.openai.com/api-keys",
        "key_placeholder": "sk-...",
        "key_hint": "OpenAI keys start with sk-.",
        "cost_note": "Paid: needs billing credit on your OpenAI API account (separate from a ChatGPT subscription).",
        "default_models": ["gpt-6-astra", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-luna"],
        "guide": [
            "Open [platform.openai.com/api-keys](https://platform.openai.com/api-keys) and sign in.",
            "Click **Create new secret key**.",
            "Copy the key. It starts with `sk-`.",
        ],
    },
    GEMINI: {
        "label": "Google Gemini",
        "name": "Gemini",
        "key_url": "https://aistudio.google.com/apikey",
        "key_placeholder": "AIza...",
        "key_hint": "Paste the full key from Google AI Studio.",
        "cost_note": "Has a free tier.",
        "default_models": ["gemini-3.8-flash"],
        "guide": [
            "Open [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and sign in with Google.",
            "Click **Create API key**.",
            "Copy the key.",
        ],
    },
    ANTHROPIC: {
        "label": "Anthropic (Claude)",
        "name": "Claude",
        "key_url": "https://platform.claude.com/settings/keys",
        "key_placeholder": "sk-ant-...",
        "key_hint": "Claude keys start with sk-ant-.",
        "cost_note": "Paid: needs credit on your Claude API account (separate from a Claude subscription).",
        "default_models": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
        "guide": [
            "Open [platform.claude.com/settings/keys](https://platform.claude.com/settings/keys) and sign in.",
            "Click **Create Key**.",
            "Copy the key. It starts with `sk-ant-`.",
        ],
    },
}

PROVIDER_ORDER = [GROQ, OPENAI, GEMINI, ANTHROPIC]

# Claude models that support server-side refusal fallbacks.
_CLAUDE_FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5")
_CLAUDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_CLAUDE_MAX_TOKENS = 16000


def supports_temperature(provider: str) -> bool:
    """Current Claude models choose their own sampling; the API rejects a temperature."""
    return provider != ANTHROPIC


def is_valid_key(provider: str, key: str) -> bool:
    """Cheap format check so obviously wrong keys never reach the provider."""
    key = (key or "").strip()
    if not key or " " in key:
        return False
    if provider == GROQ:
        return key.startswith("gsk_")
    if provider == ANTHROPIC:
        return key.startswith("sk-ant-")
    if provider == OPENAI:
        return key.startswith("sk-") and not key.startswith("sk-ant-")
    if provider == GEMINI:
        return len(key) >= 20 and not key.startswith(("sk-", "gsk_"))
    return False


_KEY_PATTERNS = [
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]+"),
    re.compile(r"gsk_[A-Za-z0-9]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{10,}"),
]


def redact_keys(text: str) -> str:
    """Remove anything that looks like an API key or bearer token from a message."""
    for pat in _KEY_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


_ERROR_HINTS = [
    (("insufficient_quota", "credit balance", "billing", "payment required", "exceeded your current quota"),
     "This API account has no credit left. Add credit with the provider, or switch to Groq, which is free."),
    (("authentication", "invalid api key", "invalid_api_key", "incorrect api key", "api key not valid",
      "invalid x-api-key", "unauthorized", "401", "permissiondenied", "permission_denied"),
     "The API key was rejected. Check that you copied the whole key and that it is still active."),
    (("rate limit", "ratelimit", "rate_limit", "429", "resource_exhausted", "too many requests", "overloaded"),
     "The AI service is busy, or the rate limit was reached. Wait a minute and try again."),
    (("declined this request",),
     "The AI declined to write this. Try rewording the request."),
    (("context length", "context_length", "maximum context", "too many tokens", "request too large", "prompt is too long"),
     "The job posting or resume is too long for this model. Try a shorter posting, or pick a different model."),
    (("model not found", "does not exist", "no such model", "invalid model", "not_found", "decommissioned", "404"),
     "That model is not available for this key. Pick a different model in the sidebar."),
    (("timeout", "timed out"),
     "The AI service took too long to respond. Try again."),
    (("connection", "connecterror", "network"),
     "Could not reach the AI service. Check your internet connection and try again."),
    (("outputparser", "invalid json", "not a json", "no subject lines", "no follow-ups", "incomplete linkedin", "output was empty"),
     "The AI replied in an unexpected format. Try again, or pick a different model."),
]


def explain_error(raw: str) -> str:
    """A plain-language explanation for a technical AI error, or '' when there is nothing useful to add."""
    low = (raw or "").lower()
    for needles, message in _ERROR_HINTS:
        if any(n in low for n in needles):
            return message
    return ""


# ----------------------------------------------------------------------
# Clients
# ----------------------------------------------------------------------
def _openai_client(provider: str, api_key: str):
    from openai import OpenAI

    if provider == GEMINI:
        return OpenAI(api_key=api_key, base_url=GEMINI_OPENAI_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    return OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)


def _anthropic_client(api_key: str):
    import anthropic

    return anthropic.Anthropic(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)


# ----------------------------------------------------------------------
# Model lists
# ----------------------------------------------------------------------
_DATED_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$|-\d{8}$")
_OPENAI_SKIP = ("audio", "realtime", "transcribe", "tts", "image", "embedding", "search",
                "instruct", "moderation", "codex", "whisper", "dall-e", "sora")
_GEMINI_SKIP = ("embedding", "image", "tts", "audio", "live", "aqa", "robotics", "computer-use", "veo", "imagen")


def _order_models(found: List[str], preferred: List[str]) -> List[str]:
    """Preferred models first (in their given order), then the rest, newest-looking first."""
    head = [m for m in preferred if m in found]
    tail = sorted((m for m in found if m not in head), reverse=True)
    return head + tail


def list_models(provider: str, api_key: str) -> List[str]:
    """
    Chat models this key can use. OpenAI and Gemini are asked live, because their
    model names change often; if that fails, the built-in defaults are returned.
    """
    defaults = list(PROVIDERS[provider]["default_models"])
    if provider not in (OPENAI, GEMINI) or not is_valid_key(provider, api_key):
        return defaults
    try:
        ids = [str(m.id) for m in _openai_client(provider, api_key).models.list()]
    except Exception:
        return defaults

    found = []
    for mid in ids:
        mid = mid.split("/", 1)[1] if mid.startswith("models/") else mid
        low = mid.lower()
        if provider == OPENAI:
            if not low.startswith(("gpt-", "chatgpt-", "o1", "o3", "o4")) or any(s in low for s in _OPENAI_SKIP):
                continue
            if _DATED_SNAPSHOT.search(low):
                continue
        else:
            if not low.startswith("gemini") or any(s in low for s in _GEMINI_SKIP):
                continue
        if mid not in found:
            found.append(mid)
    return _order_models(found, defaults) if found else defaults


# ----------------------------------------------------------------------
# Calling the models
# ----------------------------------------------------------------------
def _normalize(inp: Any) -> Tuple[str, List[Dict[str, str]]]:
    """
    Turn a LangChain prompt value, a list of role/content dicts, or a plain string
    into (system_prompt, messages). Leading assistant turns are dropped because
    these APIs expect the conversation to start with the user.
    """
    if isinstance(inp, str):
        raw: List[Any] = [{"role": "user", "content": inp}]
    elif hasattr(inp, "to_messages"):
        raw = list(inp.to_messages())
    else:
        raw = list(inp)

    system_parts: List[str] = []
    messages: List[Dict[str, str]] = []
    role_map = {"human": "user", "ai": "assistant", "user": "user", "assistant": "assistant", "system": "system"}
    for m in raw:
        if isinstance(m, dict):
            role, content = m.get("role", "user"), m.get("content", "")
        else:
            role, content = getattr(m, "type", "human"), getattr(m, "content", "")
        role = role_map.get(str(role), "user")
        content = content if isinstance(content, str) else str(content)
        if not content.strip():
            continue
        if role == "system":
            system_parts.append(content)
        else:
            messages.append({"role": role, "content": content})

    while messages and messages[0]["role"] == "assistant":
        messages.pop(0)
    if not messages:
        raise ValueError("Nothing to send: the conversation has no user message.")
    return "\n\n".join(system_parts), messages


def _call_openai_compatible(client, model: str, temperature: float, inp: Any) -> AIMessage:
    import openai

    system, messages = _normalize(inp)
    if system:
        messages = [{"role": "system", "content": system}] + messages
    try:
        res = client.chat.completions.create(model=model, messages=messages, temperature=temperature)
    except openai.BadRequestError as exc:
        # Some models only accept their default temperature; retry without it.
        if "temperature" not in str(exc).lower():
            raise
        res = client.chat.completions.create(model=model, messages=messages)
    text = (res.choices[0].message.content or "") if res.choices else ""
    return AIMessage(content=text)


def _call_claude(client, model: str, inp: Any) -> AIMessage:
    import anthropic

    system, messages = _normalize(inp)
    kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": _CLAUDE_MAX_TOKENS,
        "messages": messages,
        # Thinking is adaptive by default; effort sets how hard the model works.
        "output_config": {"effort": "medium"},
    }
    if system:
        kwargs["system"] = system

    if model in _CLAUDE_FALLBACK_MODELS:
        # If a safety classifier declines the request, let the API retry it on a
        # fallback model inside the same call instead of failing outright.
        try:
            res = client.beta.messages.create(betas=[_CLAUDE_FALLBACK_BETA], fallbacks="default", **kwargs)
        except anthropic.BadRequestError as exc:
            if "fallback" not in str(exc).lower():
                raise
            res = client.messages.create(**kwargs)
    else:
        res = client.messages.create(**kwargs)

    if res.stop_reason == "refusal":
        details = getattr(res, "stop_details", None)
        why = getattr(details, "explanation", None) or "no reason given"
        raise RuntimeError(f"Claude declined this request ({why}).")
    text = "".join(block.text for block in res.content if block.type == "text")
    return AIMessage(content=text)


def build_llm(provider: str, api_key: str, model: str, temperature: float = 0.2):
    """A LangChain Runnable for the chosen provider, usable as ``prompt | llm`` or ``llm.invoke(messages)``."""
    if provider == GROQ:
        from langchain_groq import ChatGroq

        return ChatGroq(
            temperature=temperature,
            groq_api_key=api_key,
            model_name=model,
            timeout=REQUEST_TIMEOUT_SECONDS,  # never leave a visitor on an endless spinner
        )
    if provider in (OPENAI, GEMINI):
        client = _openai_client(provider, api_key)
        return RunnableLambda(lambda inp: _call_openai_compatible(client, model, temperature, inp))
    if provider == ANTHROPIC:
        client = _anthropic_client(api_key)
        return RunnableLambda(lambda inp: _call_claude(client, model, inp))
    raise ValueError(f"Unknown AI provider: {provider}")
