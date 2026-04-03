#!/usr/bin/env python3
"""hooks/pre_compact.py"""
import sys, json
from adapter import handle_pre_compact
payload = json.loads(sys.stdin.read())
print(json.dumps(handle_pre_compact(payload)))
