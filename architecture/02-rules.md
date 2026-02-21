# Rules

This document defines every rule mercury-bot enforces. Each rule lists its rationale, the threshold chosen, and an explicit note on why it is not already covered by Ruff (`select = ["ALL"]`) or Ty.

Rules are grouped into categories. All rules emit LSP `Warning` severity unless noted otherwise.

---

## Complexity

### `CMX001` — Maximum nesting depth

**Threshold:** 4 block levels
**Severity:** Warning

Flag any function or method whose body reaches a nesting depth of 5 or more block levels (counting `if`, `else`, `elif`, `for`, `while`, `with`, `try`, `except`, `finally`, `match`, `case`). The function definition itself is level 0.

**Rationale:** Deep nesting is the single most common LLM anti-pattern. LLMs default to nesting `if` trees instead of guard clauses and early returns. McCabe complexity (Ruff `C901`) counts decision points but does not directly bound nesting depth — a chain of `if/elif/elif` has high McCabe complexity but flat nesting, while nested `if`s inside loops can reach alarming depth with a modest McCabe score. These are complementary signals.

**Not covered by Ruff/Ty:** Ruff has no rule for maximum AST nesting depth.

---

### `CMX002` — Function too long

**Threshold:** 50 lines (excluding blank lines and comment-only lines)
**Severity:** Warning

Flag any function or method whose body exceeds 50 non-blank, non-comment lines.

**Rationale:** LLMs produce long functions because they have no natural stopping point — they continue generating until the task seems done. Long functions are hard for subsequent LLM passes to reason about because they exceed the effective focus window. Ruff `PLR0915` (too-many-statements) counts AST statement nodes, not lines, and triggers at 50 statements — a different signal that misses functions with many simple one-liner statements or long string literals.

**Not covered by Ruff/Ty:** Ruff has no line-count-based function length rule.

---

### `CMX003` — File too long

**Threshold:** 400 lines
**Severity:** Warning

Flag any file exceeding 400 lines.

**Rationale:** LLMs tend to accumulate everything in one file. Large files are harder for an LLM to reason about in a single context window and signal missing module decomposition. Ruff has no file-length rule.

**Not covered by Ruff/Ty:** Not present in Ruff or Ty.

---

### `CMX004` — Arrow code (missing guard clauses)

**Threshold:** Function has a primary `if` branch that contains >70% of the function body lines, and no early return before it
**Severity:** Warning

Flag functions where the main logic is wrapped in a top-level `if` condition rather than expressed as a guard clause + early return. The canonical anti-pattern:

```python
# Bad — arrow code
def process(data):
    if data is not None:
        if data.valid:
            # ... 40 lines of logic ...

# Good — guard clauses
def process(data):
    if data is None:
        return
    if not data.valid:
        return
    # ... 40 lines of logic ...
```

**Rationale:** LLMs strongly prefer wrapping logic in positive conditions rather than rejecting early. This produces rightward-drifting "arrow code" that compounds with `CMX001`.

**Not covered by Ruff/Ty:** Not present in Ruff or Ty.

---

### `CMX005` — Excessive `**kwargs` interface

**Threshold:** Function accepts `**kwargs` with fewer than 2 explicit typed parameters
**Severity:** Warning

Flag functions whose signature is primarily `**kwargs` (with zero or one explicit named parameters). This obscures the function's actual interface.

```python
# Bad
def configure(**kwargs): ...

# Acceptable (kwargs supplements explicit params)
def configure(host: str, port: int, **kwargs): ...
```

**Rationale:** LLMs use `**kwargs` as a shortcut to avoid specifying a proper interface. This makes it impossible for Ty to type-check call sites and prevents agents from understanding what the function actually accepts.

**Not covered by Ruff/Ty:** Ruff has no rule against interface-obscuring `**kwargs` usage. Ty cannot flag this as a type error.

---

## Naming

### `NAM001` — Vague variable name

**Severity:** Warning

Flag local variables (not parameters, not loop variables, not comprehension variables) whose names appear in the vague-name list:

```
data, result, results, response, output, obj, temp, tmp, val, value,
info, item, items, thing, things, stuff, ret, res, r, ans, x_data,
my_data, the_data, new_data
```

Single-character names are already covered by Ruff `E741` for the ambiguous set (`l`, `O`, `I`). This rule targets semantically meaningless multi-character names that LLMs routinely use as catch-all variable names.

**Rationale:** LLMs default to `result = ...` before returning. These names convey no information about what the variable holds, making code harder for the next LLM pass to understand.

**Not covered by Ruff/Ty:** Ruff `E741` only covers single-char ambiguous names. No Ruff rule targets semantically vague names.

---

## Documentation

### `DOC001` — Trivial docstring

**Severity:** Warning

Flag docstrings that restate the function or class name with no additional information. Detection: the docstring, lowercased and stripped of punctuation/spaces, is a substring of or equal to the function name lowercased and split on underscores.

```python
# Bad
def calculate_total():
    """Calculate total."""
    ...

def fetch_user_data():
    """Fetch user data."""
    ...

# OK
def calculate_total():
    """Sum all line items and apply tax."""
    ...
```

**Rationale:** LLMs produce docstrings that satisfy the presence check (Ruff `D1xx`) while providing zero information. A docstring that says "Calculate total" for `calculate_total()` is worse than no docstring — it wastes tokens in an agent's context window.

**Not covered by Ruff/Ty:** Ruff checks docstring presence and formatting, not semantic content.

---

### `DOC002` — Code-restating comment

**Severity:** Warning

Flag inline comments that are a near-literal restatement of the code on the same or following line. Detection: tokenize the comment and the code; if the comment tokens are a high-overlap subset of the code tokens (>60% overlap after stripping Python keywords), flag it.

```python
# Bad
i += 1  # increment i
client = Client()  # create client
return result  # return the result

# OK
i += 1  # compensate for zero-indexing
client = Client()  # reuse connection pool from module-level singleton
```

**Rationale:** This is the most ubiquitous LLM comment pattern. These comments add no information and bloat the context window consumed by subsequent LLM reads.

**Not covered by Ruff/Ty:** Ruff `ERA001` detects commented-out code, not content-free comments.

---

### `DOC003` — Complex function missing docstring

**Threshold:** Function body > 20 lines OR nesting depth > 2, AND no docstring present
**Severity:** Warning

Flag functions that are complex enough to need explanation but have no docstring. This is stricter than Ruff `D1xx` which requires docstrings on all public functions; this rule specifically targets the combination of complexity + absence.

**Rationale:** LLMs omit docstrings on functions they consider "obvious." Functions above the complexity threshold are never obvious to the next agent reading them. This rule is intentionally scoped to complex functions to avoid overlapping too broadly with Ruff.

**Not covered by Ruff/Ty:** Ruff `D1xx` flags missing docstrings universally (on public symbols). This rule targets the complexity-gated subset and applies to private functions too.

---

## Rule Summary Table

| ID | Category | Description | Threshold |
|---|---|---|---|
| CMX001 | Complexity | Max nesting depth | 4 levels |
| CMX002 | Complexity | Function too long | 50 non-blank/comment lines |
| CMX003 | Complexity | File too long | 400 lines |
| CMX004 | Complexity | Arrow code / missing guard clauses | >70% body in top-level if |
| CMX005 | Complexity | Excessive `**kwargs` interface | <2 explicit typed params |
| NAM001 | Naming | Vague variable name | hardcoded blocklist |
| DOC001 | Documentation | Trivial docstring | name-restatement heuristic |
| DOC002 | Documentation | Code-restating comment | >60% token overlap |
| DOC003 | Documentation | Complex function missing docstring | >20 lines or depth >2 |
