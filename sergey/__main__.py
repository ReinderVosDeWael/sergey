"""Entry point: sergey [check <path>... | serve]."""

import pathlib
import typing

import typer

from sergey.rules import base as rules_base

app = typer.Typer()


def _apply_fixes(source: str, diagnostics: list[rules_base.Diagnostic]) -> str:
    """Return *source* with all fixable diagnostics applied.

    Fixes are applied from bottom to top so that earlier offsets remain valid
    after each replacement.  When multiple diagnostics share the same range
    only the first fix encountered is applied.  Additional edits attached to a
    Fix (e.g. reference renames) are collected in the same pass.
    """
    # Collect all unique (line, col, end_line, end_col, replacement) edits.
    seen: set[tuple[int, int, int, int]] = set()
    all_edits: list[tuple[int, int, int, int, str]] = []

    for diag in diagnostics:
        if diag.fix is None:
            continue
        key = (diag.line, diag.col, diag.end_line, diag.end_col)
        if key not in seen:
            seen.add(key)
            all_edits.append(
                (diag.line, diag.col, diag.end_line, diag.end_col, diag.fix.replacement)
            )
        for edit in diag.fix.additional_edits:
            ekey = (edit.line, edit.col, edit.end_line, edit.end_col)
            if ekey not in seen:
                seen.add(ekey)
                all_edits.append(
                    (edit.line, edit.col, edit.end_line, edit.end_col, edit.replacement)
                )

    # Apply bottom→top to keep earlier positions stable.
    for line, col, end_line, end_col, replacement in sorted(
        all_edits, key=lambda e: (e[0], e[1]), reverse=True
    ):
        lines = source.splitlines(keepends=True)
        start = sum(len(lines[i]) for i in range(line - 1)) + col
        end = sum(len(lines[i]) for i in range(end_line - 1)) + end_col
        source = source[:start] + replacement + source[end:]
    return source


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
    paths: list[pathlib.Path] | None,
    *,
    diff: bool,
) -> list[pathlib.Path]:
    """Expand paths and optionally the git diff into a deduplicated .py file list."""
    candidates: list[pathlib.Path] = []
    if diff:
        candidates.extend(_git_diff_python_files())
    for raw_path in paths or []:
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
        list[pathlib.Path] | None,
        typer.Argument(help="Files or directories to check."),
    ] = None,
    diff: typing.Annotated[  # noqa: FBT002
        bool,
        typer.Option("--diff", help="Check .py files changed in the current git diff."),
    ] = False,
    fix: typing.Annotated[  # noqa: FBT002
        bool,
        typer.Option("--fix", help="Apply auto-fixes for fixable violations."),
    ] = False,
) -> None:
    """Check one or more files/directories for rule violations.

    Raises:
        typer.Exit: With code 1 if any unfixed violations remain.
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

        if fix:
            fixed_source = _apply_fixes(source, diagnostics)
            if fixed_source != source:
                file_path.write_text(fixed_source)
                # Re-analyze to report any remaining violations.
                diagnostics = analyzer.analyze(fixed_source)

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
