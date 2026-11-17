"""PreToolUse hook: block destructive Bash commands on protected paths."""

import json
import re
import sys

PROTECTED = ["expense_tracker.db", ".env", "migrations/"]
DANGEROUS = re.compile(r"(?:^|[\s;&|])(rm|unlink|truncate)(?=\s)")


def main():
    data = json.load(sys.stdin)
    cmd = data.get("tool_input", {}).get("command", "")
    if DANGEROUS.search(cmd):
        for path in PROTECTED:
            if path in cmd:
                print(
                    f"BLOCKED: Cannot run destructive command on protected file: {path}",
                    file=sys.stderr,
                )
                raise SystemExit(2)


if __name__ == "__main__":
    main()
