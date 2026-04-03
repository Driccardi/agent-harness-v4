"""
Eidos — Signal Classifier & Somatic Tagger
Enriches chunks with affective metadata using third-party observer framing.
Runs asynchronously after Engram; does not block the injection path.

Somatic tags answer: "What would a neutral, attentive observer infer
about the emotional/affective state of the person or agent who produced this text?"
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import anthropic

from db import client as db

logger = logging.getLogger(__name__)

SOMATIC_REGISTERS = ["ENGAGED", "FRUSTRATED", "UNCERTAIN", "SATISFIED", "URGENT", "NEUTRAL"]


@dataclass
class SomaticTag:
    register: str          # one of SOMATIC_REGISTERS
    valence: int           # -2 to +2
    energy: int            # 0 to 4
    confidence: float      # 0.0 to 1.0
    rationale: str         # brief explanation

    def is_valid(self) -> bool:
        return (
            self.register in SOMATIC_REGISTERS
            and -2 <= self.valence <= 2
            and 0 <= self.energy <= 4
        )


SOMATIC_TAG_PROMPT = """You are a neutral, attentive observer of a human-AI interaction.

You are given a text fragment from this interaction. Your task is to infer the affective and
somatic state that a trained empathic observer would detect in this text — not what is explicitly
stated, but what the text's register, pacing, word choice, and structure reveals about the
underlying emotional and energy state.

This is third-party observation: you are not asking the author how they feel.
You are reading the somatic signal in the text itself.

Text to evaluate:
<text>
{content}
</text>

Context (do not include in output):
- Chunk type: {chunk_type}
- Turn index: {turn_index}

Respond ONLY with a JSON object, no preamble or explanation:
{{
  "register": "ENGAGED|FRUSTRATED|UNCERTAIN|SATISFIED|URGENT|NEUTRAL",
  "valence": <integer -2 to +2>,
  "energy": <integer 0 to 4>,
  "confidence": <float 0.0 to 1.0>,
  "rationale": "<one sentence explanation>"
}}

Register definitions:
- ENGAGED: active, focused, interested, collaborative
- FRUSTRATED: blocked, irritated, struggling, repeated obstacles
- UNCERTAIN: hesitant, questioning, searching, incomplete understanding
- SATISFIED: resolved, confident, pleased, task complete
- URGENT: time pressure, alarm, need for immediate action
- NEUTRAL: flat, procedural, no strong signal
"""


class Eidos:
    """
    Signal classifier.
    Processes fresh chunks from the Engram queue and enriches them
    with somatic tags and signal classification.
    """

    def __init__(
        self,
        client: Optional[anthropic.AsyncAnthropic] = None,
        model: Optional[str] = None,
    ):
        self.client = client or anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self.model = model or os.environ.get(
            "ATLAS_CLAUDE_MODEL", "claude-haiku-4-5-20251001"
        )

    async def tag_chunk(
        self,
        chunk_id: UUID,
        content: str,
        chunk_type: str,
        turn_index: int,
    ) -> Optional[SomaticTag]:
        """Classify a chunk's somatic state and write tags to the database."""

        if not content.strip() or chunk_type == "SYSTEM":
            return None

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": SOMATIC_TAG_PROMPT.format(
                        content=content[:800],
                        chunk_type=chunk_type,
                        turn_index=turn_index,
                    )
                }],
                timeout=5.0,
            )

            raw = response.content[0].text.strip()
            # Strip any accidental markdown fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)

            tag = SomaticTag(
                register=data.get("register", "NEUTRAL"),
                valence=int(data.get("valence", 0)),
                energy=int(data.get("energy", 2)),
                confidence=float(data.get("confidence", 0.5)),
                rationale=data.get("rationale", ""),
            )

            if not tag.is_valid():
                logger.warning(f"Invalid somatic tag for chunk {chunk_id}: {data}")
                return None

            # Write enrichment to database
            await db.execute(
                """
                UPDATE chunks
                SET somatic_register=$1, somatic_valence=$2, somatic_energy=$3
                WHERE chunk_id=$4
                """,
                tag.register,
                tag.valence,
                tag.energy,
                str(chunk_id),
            )

            logger.debug(
                f"Eidos tagged chunk={chunk_id} register={tag.register} "
                f"valence={tag.valence} energy={tag.energy}"
            )
            return tag

        except json.JSONDecodeError as e:
            logger.warning(f"Eidos JSON parse error for chunk {chunk_id}: {e}")
        except Exception as e:
            logger.error(f"Eidos tagging failed for chunk {chunk_id}: {e}")

        return None

    async def run_queue(self, queue: asyncio.Queue) -> None:
        """
        Continuously drain the Engram queue and tag fresh chunks.
        Designed to run as a long-lived background task.
        """
        logger.info("Eidos queue processor started")
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=30.0)
                chunk_id = UUID(item["chunk_id"])
                content = item["content"]
                chunk_type = item.get("chunk_type", "REASONING")
                turn_index = item.get("turn_index", 0)

                await self.tag_chunk(chunk_id, content, chunk_type, turn_index)
                queue.task_done()

            except asyncio.TimeoutError:
                continue  # normal — no new chunks to process
            except Exception as e:
                logger.error(f"Eidos queue processor error: {e}")
                await asyncio.sleep(1)

    async def detect_input_modality(self, payload: dict) -> str:
        """
        Infer input modality from hook payload metadata.
        Returns one of: TEXT | VOICE | CLIPBOARD | FILE_UPLOAD | API
        """
        # Claude Code CLI is always TEXT for now
        # Future: inspect payload for tool_name == "voice_transcribe" etc.
        tool_name = payload.get("tool_name", "")
        if "audio" in tool_name.lower() or "voice" in tool_name.lower():
            return "VOICE"
        if "upload" in tool_name.lower() or "file" in tool_name.lower():
            return "FILE_UPLOAD"
        return "TEXT"
