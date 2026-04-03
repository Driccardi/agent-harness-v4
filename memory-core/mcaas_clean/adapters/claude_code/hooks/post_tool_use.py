#!/usr/bin/env python3
"""hooks/post_tool_use.py"""
import sys, json
from adapter import handle_post_tool_use
payload = json.loads(sys.stdin.read())
print(json.dumps(handle_post_tool_use(payload)))
