"""Minimal LLM client: Anthropic or OpenAI over HTTPS, picked by which API key is set."""

from __future__ import annotations

import os

import requests

DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-5", "openai": "gpt-5-mini"}


def provider() -> str:
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    raise RuntimeError("Set ANTHROPIC_API_KEY or OPENAI_API_KEY (or LLM_PROVIDER=mock for a dry run).")


def complete(system: str, user: str) -> str:
    name = provider()
    model = os.getenv("LLM_MODEL") or DEFAULT_MODELS.get(name, "")
    if name == "anthropic":
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 8000,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=300,
        )
        _raise(r)
        return "".join(b.get("text", "") for b in r.json()["content"])
    if name == "openai":
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={
                "model": model,
                "max_completion_tokens": 16000,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=300,
        )
        _raise(r)
        return r.json()["choices"][0]["message"]["content"]
    if name == "mock":
        return _mock(user)
    raise RuntimeError(f"Unknown LLM_PROVIDER: {name}")


def _raise(r: requests.Response) -> None:
    if r.status_code >= 400:
        raise RuntimeError(f"LLM API error {r.status_code}: {r.text[:500]}")


def _mock(user: str) -> str:
    """Offline stand-in used for testing the pipeline without an API key."""
    import json

    feed = json.loads(user.split("FEED (JSON):\n", 1)[1])[:3]
    sections = "\n".join(
        f"### {i}. {x['name']} | {x['tagline'] or 'n/a'}\n* **Source:** {x['source']} ([link]({x['url']}))\n"
        f"* **Category:** Mock\n\n* 🎯 **What They Do:**\n  {x['details'][:200]}\n\n---\n"
        for i, x in enumerate(feed, 1)
    )
    ids = ", ".join(x["id"] for x in feed)
    return (
        "Subject Line Suggestion: 🚀 Fresh Startup Briefing: Mock run\n\n---\n"
        "## ⚡ Executive Briefing: Top Latest Startups\n\n"
        f"{sections}\n### 📊 Key Takeaways & Emerging Trends\n* **Pattern Identified:** mock\n"
        f"* **Market Insight:** mock\n\n<!-- featured: {ids} -->"
    )
