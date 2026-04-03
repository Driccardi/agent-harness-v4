"""
adapters/langchain/memory_core_callback.py
LangChain → Memory-Core adapter.

Usage:
    from memory_core_callback import MemoryCoreCallbackHandler

    handler = MemoryCoreCallbackHandler()
    llm = ChatAnthropic(callbacks=[handler])
    agent = initialize_agent(..., callbacks=[handler])
"""

from __future__ import annotations
import asyncio
import os
import sys
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../client"))
from mc_client import MemoryCoreClient, UniversalEvent, EventType, client_from_env

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
    from langchain_core.agents import AgentAction, AgentFinish
except ImportError:
    # Fallback if langchain_core not installed
    class BaseCallbackHandler:
        pass


class MemoryCoreCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback that feeds all agent events into memory-core.
    Attach to any LangChain LLM, chain, or agent via the callbacks parameter.
    """

    def __init__(
        self,
        session_id: str = "",
        client: Optional[MemoryCoreClient] = None,
        auto_inject: bool = True,
    ):
        self.session_id = session_id or os.environ.get("MC_SESSION_ID", "langchain-default")
        self.client = client or client_from_env()
        self.auto_inject = auto_inject
        self._turn_index = 0

    def _ingest(self, event: UniversalEvent) -> None:
        """Fire-and-forget ingestion."""
        try:
            asyncio.get_event_loop().run_until_complete(self.client.ingest(event))
        except RuntimeError:
            # No event loop running — use sync
            self.client.ingest_sync(event)

    def _base_kwargs(self) -> dict:
        self._turn_index += 1
        return dict(
            session_id=self.session_id,
            framework="langchain",
            turn_index=self._turn_index,
        )

    # ── Human input ───────────────────────────────────────────────────────────

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        **kwargs: Any,
    ) -> None:
        """Capture the human message being sent to the model."""
        for batch in messages:
            for msg in batch:
                content = getattr(msg, "content", str(msg))
                msg_type = type(msg).__name__
                if "Human" in msg_type or "User" in msg_type:
                    self._ingest(UniversalEvent(
                        event_type=EventType.HUMAN_TURN,
                        content=str(content),
                        model_name=serialized.get("name", ""),
                        **self._base_kwargs(),
                    ))

    # ── Model response ────────────────────────────────────────────────────────

    def on_llm_end(self, response: "LLMResult", **kwargs: Any) -> None:
        """Capture the model's response."""
        for generation_list in response.generations:
            for gen in generation_list:
                content = getattr(gen, "text", str(gen))
                self._ingest(UniversalEvent(
                    event_type=EventType.MODEL_TURN,
                    content=content,
                    **self._base_kwargs(),
                ))

    # ── Tool use ──────────────────────────────────────────────────────────────

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "unknown_tool")
        self._ingest(UniversalEvent(
            event_type=EventType.TOOL_USE,
            tool_name=tool_name,
            tool_input={"input": input_str},
            **self._base_kwargs(),
        ))

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        tool_name = kwargs.get("name", "unknown_tool")
        self._ingest(UniversalEvent(
            event_type=EventType.TOOL_RESULT,
            tool_name=tool_name,
            tool_output={"output": str(output)[:4000]},
            **self._base_kwargs(),
        ))

    # ── Agent actions ─────────────────────────────────────────────────────────

    def on_agent_action(self, action: "AgentAction", **kwargs: Any) -> None:
        self._ingest(UniversalEvent(
            event_type=EventType.TOOL_USE,
            tool_name=action.tool,
            tool_input={"input": action.tool_input},
            **self._base_kwargs(),
        ))

    def on_agent_finish(self, finish: "AgentFinish", **kwargs: Any) -> None:
        output = finish.return_values.get("output", str(finish.return_values))
        self._ingest(UniversalEvent(
            event_type=EventType.MODEL_TURN,
            content=str(output),
            **self._base_kwargs(),
        ))

    # ── Session lifecycle ─────────────────────────────────────────────────────

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> None:
        if self._turn_index == 0:
            self.client.session_start_sync(self.session_id)

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        pass  # Session end triggered externally or via explicit call

    def end_session(self) -> None:
        """Call this when your LangChain pipeline completes."""
        self.client.session_end_sync(self.session_id, self._turn_index)
