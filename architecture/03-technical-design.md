# Technical Design

## Technology Stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.14 | Matches the project Python version |
| LSP framework | `pygls` | De facto standard Python LSP library; handles JSON-RPC, stdio transport, and `lsprotocol` types |
| AST analysis | `ast` (stdlib) | Sufficient for all planned rules; no external dependency needed |
| Package manager | `uv` | Already in use for the project |

`pygls` and `lsprotocol` are the only runtime dependencies.

## Project Structure

```
sergey/
  __main__.py        # Entry point: `python -m sergey [check <file>|serve]`
  server.py          # pygls LSP server, registers handlers
  analyzer.py        # Orchestrates rule execution against a parsed AST
  rules/
    __init__.py      # Exports all rules
    base.py          # Abstract Rule class + Diagnostic dataclass
    complexity.py    # CMX001–CMX005
    naming.py        # NAM001
    documentation.py # DOC001–DOC003
tests/
  rules/
    test_complexity.py
    test_naming.py
    test_documentation.py
```

## Core Abstractions

### `Diagnostic`

```python
@dataclass
class Diagnostic:
    rule_id: str          # e.g. "CMX001"
    message: str
    line: int             # 1-indexed
    col: int              # 0-indexed
    end_line: int
    end_col: int
    severity: Severity    # enum: ERROR | WARNING | INFORMATION | HINT
```

### `Rule`

```python
class Rule(ABC):
    @abstractmethod
    def check(self, tree: ast.Module, source: str) -> list[Diagnostic]:
        ...
```

Each rule implements `check`. Rules receive both the parsed AST and the raw source string (needed for line-count rules and comment analysis). Rules must not raise — they return an empty list on any internal error.

### `Analyzer`

```python
class Analyzer:
    def __init__(self, rules: list[Rule]) -> None: ...

    def analyze(self, source: str) -> list[Diagnostic]:
        tree = ast.parse(source)
        return sorted(
            [d for rule in self.rules for d in rule.check(tree, source)],
            key=lambda d: (d.line, d.col),
        )
```

`Analyzer` is constructed once at server startup with all rules instantiated. `analyze()` is called per document.

## LSP Server

The server is minimal: it only implements the handlers needed for diagnostic publishing.

**Handlers implemented:**
- `textDocument/didOpen` → analyze and publish diagnostics
- `textDocument/didChange` → analyze and publish diagnostics
- `textDocument/didClose` → clear diagnostics

**Not implemented:** hover, completion, code actions, formatting, rename, go-to-definition.

```python
# server.py sketch
server = LanguageServer("sergey", "v0.1.0")
analyzer = Analyzer(rules=[...all rules...])

@server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls, params):
    _publish(ls, params.text_document)

def _publish(ls, text_document):
    source = ls.workspace.get_text_document(text_document.uri).source
    diagnostics = analyzer.analyze(source)
    ls.publish_diagnostics(text_document.uri, [_to_lsp(d) for d in diagnostics])
```

## CLI Mode

`python -m sergey check <file>` runs the analyzer and prints diagnostics to stdout in a human-readable format (matching Ruff's output style for consistency):

```
src/foo.py:12:4: CMX001 Function `process` exceeds maximum nesting depth of 4 (depth: 6)
src/foo.py:45:0: CMX002 Function `handle_request` is 73 lines long (max: 50)
```

Exit code 0 if no diagnostics, 1 if any warnings or errors. This makes it composable in CI and agent loops without requiring an LSP client.

## Testing Strategy

Rules are tested in isolation via the `Rule.check()` interface — no LSP server involved. Each test file provides minimal Python snippets as strings and asserts on the returned `Diagnostic` list (rule IDs, line numbers).

```python
def test_nesting_depth_exceeded():
    source = textwrap.dedent("""
        def f():
            if a:
                if b:
                    if c:
                        if d:
                            if e:  # depth 5, should warn
                                pass
    """)
    diags = CMX001().check(ast.parse(source), source)
    assert len(diags) == 1
    assert diags[0].rule_id == "CMX001"
```

Tests use `pytest`. No mocking needed — pure function input/output.

## AST Visitor Pattern

Most rules use `ast.NodeVisitor` or `ast.walk`. Nesting-depth rules require a stateful visitor that tracks depth:

```python
class NestingVisitor(ast.NodeVisitor):
    NESTING_NODES = (ast.If, ast.For, ast.While, ast.With, ast.Try,
                     ast.ExceptHandler, ast.Match, ast.match_case)

    def __init__(self):
        self.depth = 0
        self.max_depth = 0

    def visit(self, node):
        if isinstance(node, self.NESTING_NODES):
            self.depth += 1
            self.max_depth = max(self.max_depth, self.depth)
            self.generic_visit(node)
            self.depth -= 1
        else:
            self.generic_visit(node)
```

Nesting depth is measured per function body, not globally, so the visitor is reset for each `FunctionDef`/`AsyncFunctionDef`.

## Implementation Order

1. Project scaffolding: `Diagnostic`, `Rule`, `Analyzer`, CLI skeleton
2. `CMX001` (nesting depth) — most impactful, validates the visitor pattern
3. `CMX002` (function length) — simple line-count rule
4. `CMX003` (file length) — trivial
5. `DOC001` (trivial docstring) — validates string analysis approach
6. `NAM001` (vague names) — validates name-walking approach
7. `CMX004` (arrow code) — most complex detection logic
8. `CMX005` (excessive kwargs) — straightforward signature inspection
9. `DOC002` (code-restating comment) — requires tokenization
10. `DOC003` (complex function missing docstring) — combines CMX001/CMX002 signals
11. LSP server (`pygls` integration)
12. Full test coverage pass
