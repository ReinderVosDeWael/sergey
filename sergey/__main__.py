"""Entry point: sergey [check <path>... | serve]."""

import pathlib
import typing

import typer

app = typer.Typer()

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


def _git_diff_python_files() -> list[pathlib.Path]:
    """Return .py files changed relative to HEAD in the current git repository.

    Returns an empty list when git is unavailable or the directory is not a
    git repository.
    """
    import subprocess  # noqa: PLC0415

    try:
        root_proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        diff_proc = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    if root_proc.returncode != 0 or diff_proc.returncode != 0:
        return []
    git_root = pathlib.Path(root_proc.stdout.strip())
    return [
        git_root / line
        for line in diff_proc.stdout.splitlines()
        if line.endswith(".py")
    ]


def _resolve_files(
    paths: list[pathlib.Path],
    *,
    diff: bool,
) -> list[pathlib.Path]:
    """Expand paths and optionally the git diff into a deduplicated .py file list."""
    candidates: list[pathlib.Path] = []
    if diff:
        candidates.extend(_git_diff_python_files())
    for raw_path in paths:
        if raw_path.is_dir():
            candidates.extend(_collect_python_files(raw_path))
        else:
            candidates.append(raw_path)
    seen: set[pathlib.Path] = set()
    unique: list[pathlib.Path] = []
    for file_path in candidates:
        resolved = file_path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(file_path)
    return unique


@app.command(no_args_is_help=True)
def check(
    paths: typing.Annotated[
        list[pathlib.Path],
        typer.Argument(help="Files or directories to check."),
    ] = [],  # noqa: B006
    diff: typing.Annotated[  # noqa: FBT002
        bool,
        typer.Option("--diff", help="Check .py files changed in the current git diff."),
    ] = False,
) -> None:
    """Check one or more files/directories for rule violations.

    Raises:
        typer.Exit: With code 1 if any violations are found.
    """
    from sergey import analyzer as sergey_analyzer  # noqa: PLC0415
    from sergey import config as sergey_config  # noqa: PLC0415
    from sergey import rules  # noqa: PLC0415

    python_files = _resolve_files(paths, diff=diff)
    cfg = sergey_config.load_config()
    active_rules = sergey_config.filter_rules(rules.ALL_RULES, cfg)
    active_rules = sergey_config.configure_rules(active_rules, cfg)
    analyzer = sergey_analyzer.Analyzer(rules=active_rules)
    found_any = False

    for file_path in python_files:
        try:
            source = file_path.read_text()
        except OSError as e:
            typer.echo(f"error: {e}", err=True)
            continue

        diagnostics = analyzer.analyze(source)
        for diag in diagnostics:
            typer.echo(
                f"{file_path}:{diag.line}:{diag.col}: {diag.rule_id} {diag.message}"
            )
        if diagnostics:
            found_any = True

    if found_any:
        raise typer.Exit(code=1)


@app.command(no_args_is_help=True)
def serve() -> None:
    """Run the LSP server over stdio."""
    from sergey import server  # noqa: PLC0415

    server.start()


def main() -> None:
    """Dispatch to CLI check mode or LSP server mode."""
    app()


if __name__ == "__main__":
    main()
