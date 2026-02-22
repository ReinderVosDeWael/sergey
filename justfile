# Run all linters and tests
check:
    uv run ruff check .
    uv run ty check
    uv run sergey check sergey/
    uv run pytest
