"""pygls LSP server for mercury-bot."""

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from mercury_bot.analyzer import Analyzer
from mercury_bot.rules import ALL_RULES
from mercury_bot.rules.base import Diagnostic, Severity

server = LanguageServer("mercury-bot", "v0.1.0")
analyzer = Analyzer(rules=ALL_RULES)


def _to_lsp(d: Diagnostic) -> types.Diagnostic:
    """Convert a mercury-bot Diagnostic to an LSP Diagnostic."""
    severity_map = {
        Severity.ERROR: types.DiagnosticSeverity.Error,
        Severity.WARNING: types.DiagnosticSeverity.Warning,
        Severity.INFORMATION: types.DiagnosticSeverity.Information,
        Severity.HINT: types.DiagnosticSeverity.Hint,
    }
    return types.Diagnostic(
        range=types.Range(
            start=types.Position(line=d.line - 1, character=d.col),
            end=types.Position(line=d.end_line - 1, character=d.end_col),
        ),
        message=f"{d.rule_id} {d.message}",
        severity=severity_map[d.severity],
        source="mercury-bot",
    )


def _publish(ls: LanguageServer, uri: str) -> None:
    """Analyze a document and publish diagnostics to the client."""
    source = ls.workspace.get_text_document(uri).source
    diagnostics = analyzer.analyze(source)
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=uri,
            diagnostics=[_to_lsp(d) for d in diagnostics],
        )
    )


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: types.DidOpenTextDocumentParams) -> None:
    """Analyze a newly opened document."""
    _publish(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams) -> None:
    """Re-analyze a document after every change."""
    _publish(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls: LanguageServer, params: types.DidCloseTextDocumentParams) -> None:
    """Clear diagnostics when a document is closed."""
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[])
    )


def start() -> None:
    """Start the LSP server over stdio."""
    server.start_io()
