#!/usr/bin/env python3
"""hooks/pre_tool_use.py — 12 lines of actual logic."""
import sys, json
from adapter import handle_pre_tool_use
payload = json.loads(sys.stdin.read())
print(json.dumps(handle_pre_tool_use(payload)))
