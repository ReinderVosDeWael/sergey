"""Entry point: sergey [check <path>... | serve]."""

import sys
from pathlib import Path

from sergey.analyzer import Analyzer
from sergey.rules import ALL_RULES

_USAGE = "Usage: sergey [check <path>... | serve]"
_MIN_ARGS = 2
_CHECK_MIN_ARGS = 3

# Directories that are never interesting to analyse.
_SKIP_DIRS: frozenset[str] = frozenset(
    {".venv", "venv", "__pycache__", ".git", "node_modules", "build", "dist", ".tox"}
)


def _collect_python_files(root: Path) -> list[Path]:
    """Recursively find .py files under root, skipping non-source directories."""
    return sorted(
        p
        for p in root.rglob("*.py")
        if not any(part in _SKIP_DIRS for part in p.parts)
    )


def _run_check(paths: list[str]) -> None:
    """Check one or more files/directories and exit with appropriate code."""
    python_files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            python_files.extend(_collect_python_files(p))
        else:
            python_files.append(p)

    analyzer = Analyzer(rules=ALL_RULES)
    found_any = False

    for file_path in python_files:
        try:
            source = file_path.read_text()
        except OSError as e:
            sys.stderr.write(f"error: {e}\n")
            continue

        diagnostics = analyzer.analyze(source)
        for d in diagnostics:
            sys.stdout.write(f"{file_path}:{d.line}:{d.col}: {d.rule_id} {d.message}\n")
        if diagnostics:
            found_any = True

    sys.exit(1 if found_any else 0)


def main() -> None:
    """Dispatch to CLI check mode or LSP server mode."""
    if len(sys.argv) < _MIN_ARGS:
        sys.stderr.write(_USAGE + "\n")
        sys.exit(2)

    command = sys.argv[1]

    if command == "serve":
        from sergey.server import start  # noqa: PLC0415

        start()

    elif command == "check":
        if len(sys.argv) < _CHECK_MIN_ARGS:
            sys.stderr.write("Usage: sergey check <path>...\n")
            sys.exit(2)

        _run_check(sys.argv[2:])

    else:
        sys.stderr.write(f"Unknown command: {command!r}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
