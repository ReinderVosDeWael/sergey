#!/usr/bin/env python3
"""PostToolUse hook: run mercury-bot after writing or editing a Python file."""

import json
import subprocess
import sys

data = json.load(sys.stdin)
file_path: str = data.get("tool_input", {}).get("file_path", "")

if not file_path.endswith(".py"):
    sys.exit(0)

result = subprocess.run(
    ["uv", "run", "python", "-m", "mercury_bot", "check", file_path],
    capture_output=True,
    text=True,
)

if result.returncode == 0:
    sys.exit(0)

sys.stderr.write(f"mercury-bot: {file_path}\n")
sys.stderr.write(result.stdout)
sys.exit(2)
