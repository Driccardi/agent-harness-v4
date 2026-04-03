#!/usr/bin/env python3
"""hooks/session_end.py"""
import sys, json
from adapter import handle_session_end
payload = json.loads(sys.stdin.read())
print(json.dumps(handle_session_end(payload)))
