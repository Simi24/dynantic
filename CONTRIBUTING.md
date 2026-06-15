# Contributing to Dynantic

Thanks for your interest in improving Dynantic! This guide covers how to set up
the project, run the test suite, and submit changes.

## Development Setup

Dynantic uses [uv](https://docs.astral.sh/uv/) for dependency and environment
management.

```bash
git clone https://github.com/Simi24/dynantic.git
cd dynantic
uv sync --dev
```

Integration tests run against [LocalStack](https://www.localstack.cloud/) via
Docker Compose:

```bash
docker compose up -d   # start LocalStack (DynamoDB on :4566)
```

## Running Tests

```bash
# Unit tests only (fast, no Docker required)
uv run pytest -m unit

# Integration tests (requires LocalStack running)
uv run pytest -m integration

# Everything, with coverage
uv run pytest
```

## Linting & Type Checking

All code must pass `ruff` and `mypy --strict` before it can be merged:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy dynantic
```

Installing the pre-commit hooks runs these automatically on every commit:

```bash
uv run pre-commit install
```

## Commit Messages

Dynantic uses [Conventional Commits](https://www.conventionalcommits.org/).
Releases and the changelog are generated automatically by
[release-please](https://github.com/googleapis/release-please) from your commit
messages, so the prefix matters:

- `feat:` — a new feature (minor version bump)
- `fix:` — a bug fix (patch version bump)
- `docs:` — documentation only
- `refactor:`, `perf:`, `test:`, `chore:` — see the changelog sections

Breaking changes: add a `!` after the type (`feat!:`) or a `BREAKING CHANGE:`
footer.

## Pull Requests

1. Fork the repository and create a feature branch.
2. Add or update tests covering your change.
3. Make sure `ruff`, `mypy`, and the full test suite pass.
4. Update the docs (`docs/`) when you change public behavior.
5. Open a PR with a clear description and a conventional-commit title.

## Scope & Design Notes

Dynantic is **synchronous-first** and intentionally dependency-light (only
`pydantic` and `boto3`). Please avoid adding new runtime dependencies unless
strictly necessary, and keep modules small and focused.
