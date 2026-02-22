"""Entry point: sergey [check <path>... | serve]."""

import pathlib
import sys

from sergey import analyzer as sergey_analyzer
from sergey import config as sergey_config
from sergey import rules

_USAGE = "Usage: sergey [check <path>... | serve]"
_MIN_ARGS = 2
_CHECK_MIN_ARGS = 3

# Directories that are never interesting to analyse.
_SKIP_DIRS: frozenset[str] = frozenset(
    {".venv", "venv", "__pycache__", ".git", "node_modules", "build", "dist", ".tox"}
)


def _collect_python_files(root: pathlib.Path) -> list[pathlib.Path]:
    """Recursively find .py files under root, skipping non-source directories."""
    return sorted(
        py_file
        for py_file in root.rglob("*.py")
        if not any(part in _SKIP_DIRS for part in py_file.parts)
    )


def _run_check(paths: list[str]) -> None:
    """Check one or more files/directories and exit with appropriate code."""
    python_files: list[pathlib.Path] = []
    for raw in paths:
        raw_path = pathlib.Path(raw)
        if raw_path.is_dir():
            python_files.extend(_collect_python_files(raw_path))
        else:
            python_files.append(raw_path)

    cfg = sergey_config.load_config()
    active_rules = sergey_config.filter_rules(rules.ALL_RULES, cfg)
    analyzer = sergey_analyzer.Analyzer(rules=active_rules)
    found_any = False

    for file_path in python_files:
        try:
            source = file_path.read_text()
        except OSError as e:
            sys.stderr.write(f"error: {e}\n")
            continue

        diagnostics = analyzer.analyze(source)
        for diag in diagnostics:
            sys.stdout.write(
                f"{file_path}:{diag.line}:{diag.col}: {diag.rule_id} {diag.message}\n"
            )
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
        from sergey import server  # noqa: PLC0415

        server.start()

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
