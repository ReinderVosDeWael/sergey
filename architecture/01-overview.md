# Overview

## What Is mercury-bot?

mercury-bot is an opinionated Python LSP designed to run in LLM-powered coding agent loops (e.g. Claude Code, Cursor, Aider). It is **not** a replacement for Pyright or Ty — it runs alongside them. Its purpose is to catch patterns that standard type checkers and linters miss but that LLMs consistently produce: deep nesting, vague naming, long functions, low-quality comments, etc.

The target consumer of diagnostics is primarily the **LLM agent itself**, not a human reading editor output. An agent runs mercury-bot, receives structured diagnostics, and self-corrects before committing.

## Goals

- Surface code quality issues specific to LLM-generated Python that Ruff and Ty do not cover.
- Be fast enough to run on every agent iteration without significant overhead.
- Emit diagnostics in standard LSP format so editors can display them if desired.
- Be deliberately opinionated: no configuration, no per-rule toggles, no escape hatches. The rules encode a single, consistent philosophy.
- Remain complementary to existing tooling. Any issue already flagged by Ruff (with `select = ["ALL"]`) or Ty is explicitly out of scope.

## Non-Goals

- Replace or duplicate Ruff, Pyright, or Ty rules.
- Support auto-fix. Fixes require judgment; the agent applies them.
- Optimize for human editor UX (incremental parsing, hover, completion, etc.).
- Be configurable. Opinionated defaults are the point.

## Primary Deployment Model

mercury-bot is designed to run in an **agentic loop**:

```
LLM writes code → Ruff → Ty → mercury-bot → diagnostics fed back to LLM → repeat
```

It must also expose a standard LSP server for optional editor integration (e.g. a developer reviewing LLM output), but this is secondary. Editor features beyond `textDocument/publishDiagnostics` (hover, completion, etc.) are out of scope.

## Design Decisions

**Fixed rules, no configuration.** Rules encode best practices. Thresholds are chosen once and justified in `02-rules.md`. This eliminates config bikeshedding and ensures consistent behavior across all agent contexts.

**AST-based analysis only.** The standard `ast` module is sufficient for all planned rules. No type inference required (that is Ty's job). This keeps the dependency surface minimal and analysis fast.

**Whole-file analysis per request.** No incremental parsing. Agents send complete file contents; mercury-bot analyzes and responds. This is simpler and sufficient for the batch-style usage pattern.

**Stdio transport.** LSP over stdio is the standard for programmatic use. No HTTP, no WebSocket.
