"""Minimal chat. Debug version — shows every step."""
import os

import config
import data
import db


def reply(history):
    # Step 1: check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "NO API KEY FOUND. Run in PowerShell: setx ANTHROPIC_API_KEY sk-ant-your-key"
    
    # Step 2: import
    try:
        import anthropic
    except Exception as e:
        return f"IMPORT FAILED: {e}"
    
    # Step 3: create client
    try:
        client = anthropic.Anthropic()
    except Exception as e:
        return f"CLIENT FAILED: {e}"
    
    # Step 4: build messages
    messages = []
    for msg in history[-10:]:
        role = msg.get("role", "user")
        if role not in ("user", "assistant"):
            role = "user"
        content = msg.get("content", "")
        if not content:
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += " " + content
        else:
            messages.append({"role": role, "content": content})
    
    if not messages or messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "hello"})
    
    # Step 5: call API
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            system="You are a helpful mentor. Keep responses to 1-2 sentences. Plain text only, no formatting.",
            messages=messages,
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"API CALL FAILED: {e}"
