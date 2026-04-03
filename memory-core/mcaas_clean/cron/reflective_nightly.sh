#!/bin/bash
# cron/reflective_nightly.sh
# Run at 02:00 daily. Triggers the reflective memory layer for all active tenants.
# Oneiros consolidates beliefs. Psyche updates soul.md. Augur mines behavioral patterns.
#
# Crontab: 0 2 * * * /path/to/cron/reflective_nightly.sh >> /var/log/mc_reflective.log 2>&1

set -e

MC_URL="${MC_BASE_URL:-http://localhost:4200}"
MC_KEY="${MC_ADMIN_KEY}"
HUMAN_ID="${MC_HUMAN_ID:-default}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')] [reflective-nightly]"

echo "$LOG_PREFIX Starting nightly reflective consolidation for human_id=$HUMAN_ID"

# ── Oneiros: consolidate mature topics into standing beliefs ──────────────────
echo "$LOG_PREFIX Running Oneiros belief consolidation..."
RESULT=$(curl -sf -X POST "$MC_URL/v1/admin/reflective/oneiros" \
    -H "X-MC-Key: $MC_KEY" \
    -H "X-MC-Human-ID: $HUMAN_ID" \
    -H "Content-Type: application/json" \
    -d '{"min_chunks": 10, "all_topics": true}' 2>&1)
echo "$LOG_PREFIX Oneiros: $RESULT"

# ── Psyche: update self-narrative and prepare steering injection ──────────────
echo "$LOG_PREFIX Running Psyche self-reflection..."
RESULT=$(curl -sf -X POST "$MC_URL/v1/admin/reflective/psyche" \
    -H "X-MC-Key: $MC_KEY" \
    -H "X-MC-Human-ID: $HUMAN_ID" \
    -H "Content-Type: application/json" \
    -d '{"turns": 100}' 2>&1)
echo "$LOG_PREFIX Psyche: $RESULT"

# ── Augur: mine behavioral patterns from recent sessions ─────────────────────
echo "$LOG_PREFIX Running Augur behavioral mining..."
RESULT=$(curl -sf -X POST "$MC_URL/v1/admin/reflective/augur" \
    -H "X-MC-Key: $MC_KEY" \
    -H "X-MC-Human-ID: $HUMAN_ID" \
    -H "Content-Type: application/json" \
    -d '{"sessions": 20}' 2>&1)
echo "$LOG_PREFIX Augur: $RESULT"

echo "$LOG_PREFIX Nightly reflective run complete."
