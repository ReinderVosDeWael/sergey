"""pygls LSP server for sergey."""

from lsprotocol import types
from pygls.lsp import server as pygls_server

from sergey import analyzer as sergey_analyzer
from sergey import rules
from sergey.rules import base

server = pygls_server.LanguageServer("sergey", "v0.1.0")
analyzer = sergey_analyzer.Analyzer(rules=rules.ALL_RULES)


def _to_lsp(diag: base.Diagnostic) -> types.Diagnostic:
    """Convert a sergey Diagnostic to an LSP Diagnostic."""
    severity_map = {
        base.Severity.ERROR: types.DiagnosticSeverity.Error,
        base.Severity.WARNING: types.DiagnosticSeverity.Warning,
        base.Severity.INFORMATION: types.DiagnosticSeverity.Information,
        base.Severity.HINT: types.DiagnosticSeverity.Hint,
    }
    return types.Diagnostic(
        range=types.Range(
            start=types.Position(line=diag.line - 1, character=diag.col),
            end=types.Position(line=diag.end_line - 1, character=diag.end_col),
        ),
        message=f"{diag.rule_id} {diag.message}",
        severity=severity_map[diag.severity],
        source="sergey",
    )


def _publish(ls: pygls_server.LanguageServer, uri: str) -> None:
    """Analyze a document and publish diagnostics to the client."""
    source = ls.workspace.get_text_document(uri).source
    diagnostics = analyzer.analyze(source)
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=uri,
            diagnostics=[_to_lsp(diag) for diag in diagnostics],
        )
    )


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(
    ls: pygls_server.LanguageServer,
    params: types.DidOpenTextDocumentParams,
) -> None:
    """Analyze a newly opened document."""
    _publish(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(
    ls: pygls_server.LanguageServer,
    params: types.DidChangeTextDocumentParams,
) -> None:
    """Re-analyze a document after every change."""
    _publish(ls, params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
def did_close(
    ls: pygls_server.LanguageServer,
    params: types.DidCloseTextDocumentParams,
) -> None:
    """Clear diagnostics when a document is closed."""
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[])
    )


def start() -> None:
    """Start the LSP server over stdio."""
    server.start_io()
