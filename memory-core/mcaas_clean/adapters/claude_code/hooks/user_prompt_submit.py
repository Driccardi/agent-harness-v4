#!/usr/bin/env python3
"""hooks/user_prompt_submit.py"""
import sys, json
from adapter import handle_user_prompt_submit
payload = json.loads(sys.stdin.read())
print(json.dumps(handle_user_prompt_submit(payload)))
