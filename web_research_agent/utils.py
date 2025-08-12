from __future__ import annotations

from typing import List, Dict, Any
import os
import json

from dotenv import load_dotenv
import anthropic

# ✅ Use relative import so "tools" is found inside this package
from .tools import google_search, get_url_content

# Load .env locally if present (harmless in prod; Railway uses env vars)
load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def get_anthropic_client() -> anthropic.Anthropic:
    """Create an Anthropic client or raise a clear error if the key is missing."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in the environment.")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def ask_claude(prompt: str, max_tokens: int = 4096 * 2, temperature: float = 0) -> str | None:
    """Send a simple prompt to Claude and return the first text block (or None on error)."""
    client = get_anthropic_client()

    try:
        msg = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=max_tokens,
            temperature=temperature,
            system="You are a helpful AI assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        # Anthropic returns a list of content blocks; pick the first text block
        for block in getattr(msg, "content", []) or []:
            if getattr(block, "type", "") == "text":
                return getattr(block, "text", None)
        return None
    except Exception as e:
        print(f"Error calling Claude in ask_claude: {e}")
        return None


def process_anthropic_response(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    max_calls: int = 5,
    max_tokens: int = 4096 * 2,
    temperature: float = 0,
):
    """
    Recursively process Anthropic responses, handling tool use.
    Always returns an object with a `.content` list (matching Anthropic's shape),
    so callers can safely access `response.content`.
    """
    if max_calls <= 0:
        # fabricate a minimal "response-like" object with a text block
        return type(
            "Obj", (),
            {"content": [type("Block", (), {"type": "text", "text": "Max API calls reached."})()],
             "stop_reason": "end_turn"}
        )

    client = get_anthropic_client()

    try:
        resp = client.messages.create(
            model="claude-3-5-sonnet-latest",
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            system="You are a research assistant helping users find and analyze information from the web.",
        )

        # If Claude asks to use tools, execute them and continue the loop
        if getattr(resp, "stop_reason", "") == "tool_use":
            tool_outputs = []
            for block in getattr(resp, "content", []) or []:
                if getattr(block, "type", "") == "tool_use":
                    name = getattr(block, "name", "")
                    tool_input = getattr(block, "input", {}) or {}
                    try:
                        if name == "search_web":
                            results = google_search(tool_input.get("query", ""))
                            tool_outputs.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(results),
                            })
                        elif name == "fetch_page":
                            page = get_url_content(tool_input.get("url", ""))
                            tool_outputs.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": page or "Failed to fetch page",
                            })
                    except Exception as tool_err:
                        # Return a best-effort tool_result so the loop can continue
                        tool_outputs.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Tool error: {tool_err}",
                        })

            if tool_outputs:
                # Continue the conversation by feeding tool results back to Claude
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": tool_outputs})
                return process_anthropic_response(
                    messages, tools, max_calls - 1, max_tokens, temperature
                )

        # No tool call requested; return the response as-is
        return resp

    except Exception as e:
        # Fabricate a response-like object with a JSON payload in a text block,
        # so upstream code that expects `response.content[0].text` can still parse.
        fallback_json = json.dumps({"results": [], "comments": f"Error: {e}", "next_action": ""})
        return type(
            "Obj", (),
            {"content": [type("Block", (), {"type": "text", "text": fallback_json})()],
             "stop_reason": "end_turn"}
        )
