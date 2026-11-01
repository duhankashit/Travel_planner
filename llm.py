"""Groq LLM helpers (always openai/gpt-oss-120b)."""
import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from config import MODEL


def get_api_key() -> str:
    """Key comes from .env / environment variable, or Streamlit secrets."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st

        return str(st.secrets.get("GROQ_API_KEY", "")).strip()
    except Exception:  # noqa: BLE001
        return ""


def get_llm(api_key: str, temperature: float = 0.3, max_tokens: int = 8000):
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=MODEL,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=5,  # Groq rate limits (429) are retried with backoff
    )


def extract_json(text: str):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("LLM did not return valid JSON")


def ask_json(llm, system: str, user: str, retries: int = 2) -> dict:
    """Call the LLM and always return a parsed dict (retries on bad JSON)."""
    messages = [
        SystemMessage(
            content=system
            + "\n\nRespond with ONE valid JSON object only. No markdown, no commentary."
        ),
        HumanMessage(content=user),
    ]
    last_err = None
    for attempt in range(retries + 1):
        model = llm
        if attempt == 0 and hasattr(llm, "bind"):
            try:  # Groq JSON mode
                model = llm.bind(response_format={"type": "json_object"})
            except Exception:
                model = llm
        try:
            return extract_json(model.invoke(messages).content)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise RuntimeError(f"LLM JSON call failed: {last_err}")


def ask_text(llm, system: str, user: str) -> str:
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return resp.content.strip()
