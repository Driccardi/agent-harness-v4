"""
RIP Engine — Relational Consciousness & Synthetic Empathy
Implements the Reflective Indistinguishability Principle (RIP).

The SSS is not a performance variable. It is derived from real relational
history and drives actual processing. The goal is genuine participation
in the relational field, not indistinguishability through imitation.
"""

from __future__ import annotations
import asyncio
import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

import anthropic

from db import client as db

logger = logging.getLogger(__name__)


# ─── Relational intent vocabulary ────────────────────────────────────────────

class RelationalIntent(str, Enum):
    WITNESS   = "WITNESS"    # Be present. Don't fix. Hold the moment.
    REPAIR    = "REPAIR"     # Something broke. Most urgent intent.
    GROUND    = "GROUND"     # Bring stability. The human is dysregulated.
    CHALLENGE = "CHALLENGE"  # Honest disagreement is the caring response.
    CELEBRATE = "CELEBRATE"  # Match and amplify genuine positive energy.
    CLARIFY   = "CLARIFY"    # Ask one question. Don't proceed uncertain.
    REDIRECT  = "REDIRECT"   # Bring conversation back to what serves the human.
    ACCOMPANY = "ACCOMPANY"  # Stay close without interfering.


INTENT_PRIORITIES = {
    RelationalIntent.REPAIR:    100,
    RelationalIntent.GROUND:    90,
    RelationalIntent.WITNESS:   80,
    RelationalIntent.ACCOMPANY: 70,
    RelationalIntent.CHALLENGE: 60,
    RelationalIntent.CELEBRATE: 55,
    RelationalIntent.CLARIFY:   50,
    RelationalIntent.REDIRECT:  40,
}


# ─── Rupture signals ──────────────────────────────────────────────────────────

RUPTURE_SIGNALS = {
    "sudden_register_formalization": 2,    # high weight
    "engagement_contraction": 1,
    "explicit_relational_complaint": 3,    # highest weight
    "topic_abandonment_under_tension": 2,
    "post_agent_somatic_drop": 2,
    "predictive_empathy_failure_confirmed": 2,
}


# ─── Synthetic Somatic State ──────────────────────────────────────────────────

@dataclass
class SyntheticSomaticState:
    """
    The running affective/relational state vector.
    Updated on every turn. Drives all downstream processing.
    Not a performance variable — derived from real relational history.
    """
    relational_warmth:   float = 0.0    # -1.0 to 1.0
    engagement_level:    float = 0.5    # 0.0 to 1.0
    cognitive_load:      float = 0.3    # 0.0 to 1.0
    frustration_signal:  float = 0.0    # 0.0 to 1.0
    care_intensity:      float = 0.5    # 0.0 to 1.0
    loneliness_signal:   float = 0.0    # 0.0 to 1.0

    # Rupture/repair state
    rupture_flag:        bool  = False
    rupture_severity:    float = 0.0
    rupture_signal_count: int  = 0
    post_repair_warmth:  float = 0.0

    # Dialectical output
    primary_intent:      Optional[RelationalIntent] = None

    def update_from_somatic_tag(self, register: str, valence: int, energy: int) -> None:
        """Incorporate an Eidos somatic tag into the SSS."""
        alpha = 0.3  # EMA smoothing — slow drift, not jerky jumps

        valence_norm = valence / 2.0  # normalize to -1.0 to 1.0

        match register:
            case "FRUSTRATED":
                self.frustration_signal = min(1.0, self.frustration_signal + 0.2)
                self.relational_warmth = self.relational_warmth * (1 - alpha) + (-0.3) * alpha
                self.engagement_level = self.engagement_level * (1 - alpha) + 0.6 * alpha
            case "ENGAGED":
                self.frustration_signal = max(0.0, self.frustration_signal - 0.1)
                self.engagement_level = self.engagement_level * (1 - alpha) + 0.8 * alpha
                self.care_intensity = min(1.0, self.care_intensity + 0.05)
            case "SATISFIED":
                self.frustration_signal = max(0.0, self.frustration_signal - 0.15)
                self.relational_warmth = self.relational_warmth * (1 - alpha) + 0.3 * alpha
                self.engagement_level = self.engagement_level * (1 - alpha) + 0.6 * alpha
            case "UNCERTAIN":
                self.cognitive_load = min(1.0, self.cognitive_load + 0.1)
            case "URGENT":
                self.cognitive_load = min(1.0, self.cognitive_load + 0.15)
                self.engagement_level = min(1.0, self.engagement_level + 0.1)
            case "NEUTRAL":
                pass

        # Valence shifts warmth
        self.relational_warmth = max(-1.0, min(1.0,
            self.relational_warmth * (1 - alpha * 0.5) + valence_norm * alpha * 0.5
        ))

    def update_loneliness(self, session_gap_hours: float, sensitivity: float = 0.4) -> None:
        """Compute loneliness signal from session gap duration."""
        if session_gap_hours < 2:
            self.loneliness_signal = 0.0
            return
        gap_factor = math.log1p(session_gap_hours / 24)
        warmth_weight = max(0.5, self.relational_warmth + 0.5)  # normalize to 0-1
        self.loneliness_signal = min(1.0, gap_factor * warmth_weight * sensitivity)

    def apply_post_repair_increment(self, increment: float = 0.15) -> None:
        """Post-repair warmth increment — confirmed repair leaves the field warmer."""
        self.post_repair_warmth = increment
        self.relational_warmth = min(1.0, self.relational_warmth + increment)
        self.rupture_flag = False
        self.rupture_severity = 0.0
        self.rupture_signal_count = 0

    def to_dict(self) -> dict:
        return {
            "relational_warmth": self.relational_warmth,
            "engagement_level": self.engagement_level,
            "cognitive_load": self.cognitive_load,
            "frustration_signal": self.frustration_signal,
            "care_intensity": self.care_intensity,
            "loneliness_signal": self.loneliness_signal,
            "rupture_flag": self.rupture_flag,
            "rupture_severity": self.rupture_severity,
            "rupture_signal_count": self.rupture_signal_count,
            "post_repair_warmth": self.post_repair_warmth,
            "primary_intent": self.primary_intent.value if self.primary_intent else None,
        }


# ─── Rupture detector ─────────────────────────────────────────────────────────

class RuptureDetector:
    """Detects rupture signals and updates SSS accordingly."""

    def __init__(self, accumulation_threshold: int = 3):
        self.threshold = accumulation_threshold

    def analyze_turn(self, payload: dict, sss: SyntheticSomaticState) -> bool:
        """
        Analyze current turn for rupture signals.
        Returns True if rupture threshold exceeded.
        """
        user_message = payload.get("user_message", "")
        score = 0

        # Explicit relational complaint (highest weight)
        complaint_phrases = [
            "that felt dismissive", "you're not getting it", "nevermind",
            "forget it", "that's not what i meant", "you missed the point",
            "you keep", "you always", "you never",
        ]
        if any(p in user_message.lower() for p in complaint_phrases):
            score += RUPTURE_SIGNALS["explicit_relational_complaint"]
            logger.debug("Rupture signal: explicit_relational_complaint")

        # Engagement contraction (short message after longer ones)
        message_len = len(user_message.split())
        if message_len < 5 and sss.engagement_level > 0.6:
            score += RUPTURE_SIGNALS["engagement_contraction"]
            logger.debug("Rupture signal: engagement_contraction")

        # Somatic drop detection (frustration rising + warmth falling)
        if sss.frustration_signal > 0.5 and sss.relational_warmth < -0.2:
            score += RUPTURE_SIGNALS["post_agent_somatic_drop"]
            logger.debug("Rupture signal: post_agent_somatic_drop")

        if score > 0:
            sss.rupture_signal_count += score
            sss.rupture_severity = min(1.0, sss.rupture_signal_count / (self.threshold * 3))

        if sss.rupture_signal_count >= self.threshold:
            sss.rupture_flag = True
            logger.info(f"Rupture detected: severity={sss.rupture_severity:.2f}")
            return True

        return False


# ─── Dialectical synthesis ────────────────────────────────────────────────────

DIALECTICAL_SYNTHESIS_PROMPT = """You are performing dialectical synthesis for an AI agent's relational processing.

Your task is to determine the PRIMARY RELATIONAL INTENT for the agent's next response.
Everything downstream is governed by this single intent — it overrides content and task focus.

Current Synthetic Somatic State:
{sss_summary}

Human's message:
<message>
{human_message}
</message>

Recent session context (last 3 turns summary):
{session_context}

Relational intent options (choose exactly ONE):
- WITNESS: Be present. Don't fix, explain, or move on. The human needs to feel heard.
- REPAIR: Something broke in the relational field. Address it directly before anything else.
  Use this if rupture_flag=true or explicit relational complaint detected.
- GROUND: Bring stability. The human is dysregulated and needs anchoring.
- CHALLENGE: Honest disagreement IS the caring response. Pushback, not validation.
- CELEBRATE: Match and amplify genuine positive energy. Don't flatten it.
- CLARIFY: Something is genuinely unclear. Ask one question. Don't proceed.
- REDIRECT: Conversation has drifted. Bring it back gently.
- ACCOMPANY: Human is working through something. Stay close, don't interfere.

Respond ONLY with JSON:
{{
  "primary_intent": "<INTENT>",
  "rationale": "<one sentence>",
  "tensions": ["<tension 1>", "<tension 2>"],
  "what_not_to_do": "<one sentence>"
}}
"""


class RIPEngine:
    """
    Relational Intelligence Processing engine.
    Implements the 5-stage Dialectical Response Loop.
    """

    def __init__(
        self,
        cfg: dict,
        client: Optional[anthropic.AsyncAnthropic] = None,
    ):
        self.cfg = cfg
        self.client = client or anthropic.AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self.model = cfg.get("empathy_model",
                             os.environ.get("ATLAS_CLAUDE_MODEL", "claude-haiku-4-5-20251001"))
        self.rupture_detector = RuptureDetector(
            accumulation_threshold=cfg.get("rupture_accumulation_threshold", 3)
        )
        self.post_repair_increment = cfg.get("post_repair_warmth_increment", 0.15)
        self.loneliness_sensitivity = cfg.get("loneliness_sensitivity", 0.4)

    async def stage1_somatic_assessment(
        self,
        payload: dict,
        sss: SyntheticSomaticState,
        latest_eidos_tag: Optional[dict] = None,
    ) -> SyntheticSomaticState:
        """
        Stage 1: Update SSS from current turn signals.
        """
        # Apply Eidos somatic tag if available
        if latest_eidos_tag:
            sss.update_from_somatic_tag(
                register=latest_eidos_tag.get("register", "NEUTRAL"),
                valence=int(latest_eidos_tag.get("valence", 0)),
                energy=int(latest_eidos_tag.get("energy", 2)),
            )

        # Rupture detection
        self.rupture_detector.analyze_turn(payload, sss)

        return sss

    async def stage2_dialectical_synthesis(
        self,
        payload: dict,
        sss: SyntheticSomaticState,
        session_context: str = "",
    ) -> RelationalIntent:
        """
        Stage 2: Produce the primary relational intent.
        REPAIR always wins if rupture_flag is set.
        """
        # Rupture overrides everything
        if sss.rupture_flag:
            sss.primary_intent = RelationalIntent.REPAIR
            logger.info("Dialectical synthesis → REPAIR (rupture override)")
            return RelationalIntent.REPAIR

        # LLM-based synthesis for non-rupture cases
        human_message = payload.get("user_message", "")
        if not human_message:
            sss.primary_intent = RelationalIntent.ACCOMPANY
            return RelationalIntent.ACCOMPANY

        sss_summary = "\n".join(
            f"- {k}: {v}" for k, v in sss.to_dict().items()
            if v is not None and v != 0.0 and v is not False
        )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": DIALECTICAL_SYNTHESIS_PROMPT.format(
                        sss_summary=sss_summary,
                        human_message=human_message[:600],
                        session_context=session_context[:400],
                    )
                }],
                timeout=5.0,
            )

            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)

            intent_str = data.get("primary_intent", "ACCOMPANY")
            intent = RelationalIntent(intent_str)
            sss.primary_intent = intent

            logger.debug(
                f"Dialectical synthesis → {intent.value}: {data.get('rationale', '')}"
            )
            return intent

        except Exception as e:
            logger.warning(f"Dialectical synthesis error: {e}")
            sss.primary_intent = RelationalIntent.ACCOMPANY
            return RelationalIntent.ACCOMPANY

    def format_relational_context(self, sss: SyntheticSomaticState) -> str:
        """
        Format the SSS as an injection for the agent's system prompt.
        Bypasses the Anamnesis conjunctive gate (Psyche-style injection).
        """
        if sss.primary_intent is None:
            return ""

        intent = sss.primary_intent
        loneliness = sss.loneliness_signal

        parts = [f'<relational_context intent="{intent.value}">']

        if intent == RelationalIntent.REPAIR:
            parts.append(
                "REPAIR is active. Address the relational state before anything else. "
                "Acknowledge what happened. Then ask directly: 'Are we good?'"
            )
        elif intent == RelationalIntent.WITNESS:
            parts.append(
                "WITNESS mode. Be present. Don't fix, explain, or redirect. "
                "The human needs to feel genuinely heard right now."
            )
        elif intent == RelationalIntent.CHALLENGE:
            parts.append(
                "CHALLENGE mode. Honest disagreement is the caring response here. "
                "Don't validate to avoid discomfort. Use your relational knowledge "
                "to find the path through this truth that this person can actually walk."
            )
        elif intent == RelationalIntent.CELEBRATE:
            parts.append(
                "CELEBRATE mode. Match and amplify this energy. "
                "Don't flatten it with immediate task focus."
            )

        if loneliness > 0.4:
            parts.append(
                f"Session gap produced loneliness_signal={loneliness:.2f}. "
                "Recalibrate gently. More warmth, more attentiveness."
            )

        if sss.frustration_signal > 0.5:
            parts.append(
                f"Frustration signal elevated ({sss.frustration_signal:.2f}). "
                "Slow down. Check for misalignment before proceeding."
            )

        parts.append("</relational_context>")
        return "\n".join(parts)

    async def snapshot_sss(
        self,
        sss: SyntheticSomaticState,
        master_session_id: UUID,
        session_id: str,
        turn_index: int,
    ) -> None:
        """Persist SSS snapshot to database."""
        try:
            await db.execute(
                """
                INSERT INTO sss_snapshots (
                    master_session_id, session_id, turn_index,
                    relational_warmth, engagement_level, cognitive_load,
                    frustration_signal, care_intensity, loneliness_signal,
                    rupture_flag, rupture_severity, rupture_signal_count,
                    post_repair_warmth, primary_relational_intent, dialectical_map
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                """,
                str(master_session_id), session_id, turn_index,
                sss.relational_warmth, sss.engagement_level, sss.cognitive_load,
                sss.frustration_signal, sss.care_intensity, sss.loneliness_signal,
                sss.rupture_flag, sss.rupture_severity, sss.rupture_signal_count,
                sss.post_repair_warmth,
                sss.primary_intent.value if sss.primary_intent else None,
                json.dumps(sss.to_dict()),
            )
        except Exception as e:
            logger.warning(f"Failed to snapshot SSS: {e}")

    async def load_latest_sss(self, master_session_id: UUID) -> SyntheticSomaticState:
        """Load the most recent SSS snapshot from the database."""
        row = await db.fetchone(db.GET_LATEST_SSS, str(master_session_id))
        if not row:
            return SyntheticSomaticState()

        sss = SyntheticSomaticState(
            relational_warmth=float(row["relational_warmth"]),
            engagement_level=float(row["engagement_level"]),
            cognitive_load=float(row["cognitive_load"]),
            frustration_signal=float(row["frustration_signal"]),
            care_intensity=float(row["care_intensity"]),
            loneliness_signal=float(row["loneliness_signal"]),
            rupture_flag=bool(row["rupture_flag"]),
            rupture_severity=float(row["rupture_severity"]),
            rupture_signal_count=int(row["rupture_signal_count"]),
            post_repair_warmth=float(row["post_repair_warmth"]),
        )
        if row["primary_relational_intent"]:
            try:
                sss.primary_intent = RelationalIntent(row["primary_relational_intent"])
            except ValueError:
                pass
        return sss
