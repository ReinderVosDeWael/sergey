"""Entry point: python -m mercury_bot [check <file> | serve]."""

import sys
from pathlib import Path

from mercury_bot.analyzer import Analyzer
from mercury_bot.rules import ALL_RULES

_USAGE = "Usage: python -m mercury_bot [check <file> | serve]"
_MIN_ARGS = 2
_CHECK_MIN_ARGS = 3


def main() -> None:
    """Dispatch to CLI check mode or LSP server mode."""
    if len(sys.argv) < _MIN_ARGS:
        sys.stderr.write(_USAGE + "\n")
        sys.exit(2)

    command = sys.argv[1]

    if command == "serve":
        from mercury_bot.server import start  # noqa: PLC0415

        start()

    elif command == "check":
        if len(sys.argv) < _CHECK_MIN_ARGS:
            sys.stderr.write("Usage: python -m mercury_bot check <file>\n")
            sys.exit(2)

        path = sys.argv[2]

        try:
            source = Path(path).read_text()
        except OSError as e:
            sys.stderr.write(f"error: {e}\n")
            sys.exit(2)

        analyzer = Analyzer(rules=ALL_RULES)
        diagnostics = analyzer.analyze(source)

        for d in diagnostics:
            sys.stdout.write(f"{path}:{d.line}:{d.col}: {d.rule_id} {d.message}\n")

        sys.exit(1 if diagnostics else 0)

    else:
        sys.stderr.write(f"Unknown command: {command!r}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
