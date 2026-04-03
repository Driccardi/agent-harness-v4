"""
adapters/openai/memory_core_middleware.py
OpenAI Python SDK → Memory-Core adapter.

Usage:
    from memory_core_middleware import MemoryCoreOpenAIWrapper

    client = MemoryCoreOpenAIWrapper(openai_client=openai.AsyncOpenAI())
    response = await client.chat("gpt-4o", messages, session_id="session-1")
"""

from __future__ import annotations
import os, sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../client"))
from mc_client import MemoryCoreClient, UniversalEvent, EventType, client_from_env


class MemoryCoreOpenAIWrapper:
    """
    Thin wrapper around openai.AsyncOpenAI that feeds events into memory-core.
    """

    def __init__(
        self,
        openai_client=None,
        mc_client: Optional[MemoryCoreClient] = None,
        session_id: str = "",
    ):
        self._openai = openai_client
        self._mc = mc_client or client_from_env()
        self.session_id = session_id or os.environ.get("MC_SESSION_ID", "openai-default")
        self._turn_index = 0

    async def chat(
        self,
        model: str,
        messages: list[dict],
        **kwargs,
    ):
        """
        Drop-in replacement for openai_client.chat.completions.create().
        Intercepts the conversation and feeds events into memory-core.
        """
        # Ingest the last human message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                await self._mc.ingest(UniversalEvent(
                    event_type=EventType.HUMAN_TURN,
                    content=msg.get("content", ""),
                    session_id=self.session_id,
                    framework="openai",
                    model_name=model,
                    turn_index=self._turn_index,
                ))
                break

        # Get injection (pre-call hook equivalent)
        injection = await self._mc.get_injection(
            hook_type="PreToolUse",
            session_id=self.session_id,
            turn_index=self._turn_index,
        )

        # Inject memory context into system message if present
        if injection.inject and injection.system_message:
            system_injection = {"role": "system", "content": injection.system_message}
            messages = [system_injection] + messages

        # Call the actual OpenAI API
        response = await self._openai.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )

        # Ingest the model response
        self._turn_index += 1
        if response.choices:
            content = response.choices[0].message.content or ""
            await self._mc.ingest(UniversalEvent(
                event_type=EventType.MODEL_TURN,
                content=content,
                session_id=self.session_id,
                framework="openai",
                model_name=model,
                turn_index=self._turn_index,
            ))

        return response
