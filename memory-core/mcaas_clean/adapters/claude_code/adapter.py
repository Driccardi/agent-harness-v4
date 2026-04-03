"""
adapters/claude_code/adapter.py
Claude Code → Memory-Core adapter.

This is the entire Claude Code integration. All six hooks are HTTP calls.
The adapter translates Claude Code's hook payload format into UniversalEvents
and calls the memory-core container API.
"""

from __future__ import annotations
import json
import os
import sys
from pathlib import Path

# Add client to path (adjust if installed as package)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "client"))

from mc_client import MemoryCoreClient, UniversalEvent, EventType, client_from_env


def translate_hook_to_events(payload: dict, human_id: str) -> list[UniversalEvent]:
    """
    Translate a Claude Code hook payload into one or more UniversalEvents.
    This is the only Claude Code-specific logic.
    """
    hook_type = payload.get("hook_type", "")
    session_id = payload.get("session_id", "")
    turn_index = payload.get("turn_index", 0)
    model_name = payload.get("model", "")
    context_tokens = payload.get("context_tokens")

    base = dict(
        human_id=human_id,
        agent_id=os.environ.get("MC_AGENT_ID", "claude-code"),
        session_id=session_id,
        framework="claude_code",
        turn_index=turn_index,
        model_name=model_name or None,
        context_tokens=context_tokens,
        metadata={"hook_type": hook_type},
    )

    events = []

    if hook_type == "UserPromptSubmit":
        msg = payload.get("user_message", "")
        if msg:
            events.append(UniversalEvent(
                event_type=EventType.HUMAN_TURN,
                content=msg,
                input_modality=payload.get("input_modality", "TEXT"),
                **base,
            ))

    elif hook_type == "PreToolUse":
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})
        events.append(UniversalEvent(
            event_type=EventType.TOOL_USE,
            tool_name=tool_name,
            tool_input=tool_input,
            **base,
        ))

    elif hook_type == "PostToolUse":
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})
        tool_output = payload.get("tool_output", {})
        # Both input and output captured at PostToolUse
        if tool_input:
            events.append(UniversalEvent(
                event_type=EventType.TOOL_USE,
                tool_name=tool_name,
                tool_input=tool_input,
                **base,
            ))
        if tool_output is not None:
            events.append(UniversalEvent(
                event_type=EventType.TOOL_RESULT,
                tool_name=tool_name,
                tool_output=tool_output,
                **base,
            ))

    return events


# ─── Hook handlers ────────────────────────────────────────────────────────────

def handle_session_start(payload: dict) -> dict:
    client = client_from_env()
    result = client.session_start_sync(
        session_id=payload.get("session_id", ""),
        project_id=payload.get("project_id", ""),
    )

    response = {"continue": True}
    injections = []

    if result.orient_injection:
        injections.append(result.orient_injection)
    if result.augur_briefing:
        injections.append(result.augur_briefing)

    if injections:
        response["systemMessage"] = "\n\n".join(injections)

    # Store master_session_id for subsequent hooks
    if result.master_session_id:
        response["env"] = {"MC_MASTER_SESSION_ID": result.master_session_id}

    return response


def handle_pre_tool_use(payload: dict) -> dict:
    client = client_from_env()
    human_id = client.human_id

    # Ingest TOOL_USE event (fire-and-forget, don't await result)
    events = translate_hook_to_events(payload, human_id)
    for event in events:
        client.ingest_sync(event)

    # Get injection (latency-sensitive)
    injection = client.get_injection_sync(
        hook_type="PreToolUse",
        session_id=payload.get("session_id", ""),
        tool_name=payload.get("tool_name", ""),
        turn_index=payload.get("turn_index", 0),
    )

    result = {"continue": True}
    if injection.inject and injection.system_message:
        result["systemMessage"] = injection.system_message

    return result


def handle_post_tool_use(payload: dict) -> dict:
    client = client_from_env()
    human_id = client.human_id

    events = translate_hook_to_events(payload, human_id)
    for event in events:
        client.ingest_sync(event)

    return {"continue": True}


def handle_user_prompt_submit(payload: dict) -> dict:
    client = client_from_env()
    human_id = client.human_id

    events = translate_hook_to_events(payload, human_id)
    for event in events:
        client.ingest_sync(event)

    # Get injection with relational context
    injection = client.get_injection_sync(
        hook_type="UserPromptSubmit",
        session_id=payload.get("session_id", ""),
        turn_index=payload.get("turn_index", 0),
    )

    result = {"continue": True}
    if injection.inject and injection.system_message:
        result["systemMessage"] = injection.system_message

    return result


def handle_pre_compact(payload: dict) -> dict:
    client = client_from_env()
    injection = client.get_injection_sync(
        hook_type="PreCompact",
        session_id=payload.get("session_id", ""),
        turn_index=payload.get("turn_index", 0),
    )

    result = {"continue": True}
    if injection.additional_context:
        result["additionalContext"] = injection.additional_context

    return result


def handle_session_end(payload: dict) -> dict:
    client = client_from_env()
    client.session_end_sync(
        session_id=payload.get("session_id", ""),
        turn_count=payload.get("turn_index", 0),
    )
    return {"continue": True}
