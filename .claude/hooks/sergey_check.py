#!/usr/bin/env python3
"""PostToolUse hook: run sergey after writing or editing a Python file."""

import json
import subprocess
import sys

data = json.load(sys.stdin)
file_path: str = data.get("tool_input", {}).get("file_path", "")

if not file_path.endswith(".py"):
    sys.exit(0)

result = subprocess.run(
    ["uv", "run", "python", "-m", "sergey", "check", file_path],
    capture_output=True,
    text=True,
    check=False,
)

if result.returncode == 0:
    sys.exit(0)

sys.stderr.write(f"sergey: {file_path}\n")
sys.stderr.write(result.stdout)
sys.exit(2)
