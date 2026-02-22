"""Entry point: sergey [check <path>... | serve]."""

import pathlib  # noqa: TC003
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


@app.command(no_args_is_help=True)
def check(
    paths: typing.Annotated[
        list[pathlib.Path],
        typer.Argument(help="Files or directories to check."),
    ],
) -> None:
    """Check one or more files/directories for rule violations.

    Raises:
        typer.Exit: With code 1 if any violations are found.
    """
    from sergey import analyzer as sergey_analyzer  # noqa: PLC0415
    from sergey import config as sergey_config  # noqa: PLC0415
    from sergey import rules  # noqa: PLC0415

    python_files: list[pathlib.Path] = []
    for raw_path in paths:
        if raw_path.is_dir():
            python_files.extend(_collect_python_files(raw_path))
        else:
            python_files.append(raw_path)

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
