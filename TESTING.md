# Dynantic Testing Documentation

This document provides comprehensive information about the testing setup for the Dynantic project.

## Overview

Dynantic uses a comprehensive testing strategy that includes:
- **Unit tests** with mocked dependencies for fast, isolated testing
- **Integration tests** against LocalStack for realistic DynamoDB interactions
- **Edge case and error handling tests** for robustness
- **Continuous Integration** with GitHub Actions

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                 # Shared pytest fixtures and configuration
├── helpers/
│   ├── __init__.py
│   └── localstack.py          # LocalStack helper utilities
├── integration/               # Integration tests (require LocalStack)
│   ├── __init__.py
│   ├── test_crud_integration.py    # CRUD operations
│   ├── test_query_integration.py   # Query operations
│   ├── test_scan_integration.py    # Scan operations
│   └── test_errors.py              # Error handling and edge cases
├── models/                    # Test model definitions (if needed)
│   └── __init__.py
└── unit/                      # Unit tests (mocked dependencies)
    ├── __init__.py
    ├── test_config.py         # Model configuration tests
    ├── test_fields.py         # Field definition tests
    ├── test_metaclass.py      # DynamoMeta metaclass tests
    ├── test_model_unit.py     # DynamoModel unit tests
    ├── test_query_unit.py     # DynamoQueryBuilder unit tests
    ├── test_serializer.py     # DynamoSerializer tests
    └── test_*.py              # Additional unit tests
```

## Prerequisites

### Local Development

1. **Python 3.10+** - Required for the project
2. **uv** - Modern Python package manager (recommended)
3. **Docker** - Required for LocalStack
4. **LocalStack** - Local AWS services emulation

### Installation

```bash
# Install dependencies
uv sync --dev

# Or with pip
pip install -e ".[dev]"
```

## Running Tests

### Quick Start

```bash
# Run all tests
uv run pytest

# Run unit tests only (fast)
uv run pytest tests/unit/

# Run integration tests (requires LocalStack)
uv run pytest tests/integration/

# Run with coverage
uv run pytest --cov=dynantic
```

### Test Categories

#### Unit Tests (`pytest -m unit` or `pytest tests/unit/`)

- **Fast**: No external dependencies
- **Isolated**: All AWS services mocked
- **Comprehensive**: Test all code paths and edge cases
- **CI**: Always run in CI pipeline

```bash
# Run unit tests
uv run pytest tests/unit/ -v
```

#### Integration Tests (`pytest -m integration` or `pytest tests/integration/`)

- **Realistic**: Use LocalStack for actual DynamoDB API calls
- **Slow**: Require Docker and LocalStack startup
- **Comprehensive**: Test real serialization/deserialization
- **CI**: Run in CI with LocalStack service

```bash
# Start LocalStack (in another terminal)
docker compose up localstack

# Run integration tests
uv run pytest tests/integration/ -v
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only slow tests
pytest -m slow

# Skip slow tests
pytest -m "not slow"
```

### LocalStack Setup

For integration tests, you need LocalStack running:

```bash
# Using Docker Compose (recommended)
docker compose up localstack

# Or using Docker directly
docker run --rm -d \
  --name localstack \
  -p 4566:4566 \
  -e SERVICES=dynamodb \
  localstack/localstack:3.0
```

Wait for LocalStack to be ready:
```bash
curl http://localhost:4566/_localstack/health
```

## Test Fixtures

### Shared Fixtures (conftest.py)

#### Unit Test Fixtures

- `mock_client`: Fully mocked boto3 DynamoDB client
- `sample_user_model`: User model class for testing (partition key only)
- `sample_message_model`: Message model class for testing (partition + sort key)
- `inject_mock_client`: Injects mock client into test models

#### Integration Test Fixtures

- `localstack_client`: Real boto3 client connected to LocalStack
- `localstack_helper`: LocalStackHelper utility class
- `integration_user_model`: User model configured for LocalStack
- `integration_message_model`: Message model configured for LocalStack
- `clean_integration_tables`: Ensures fresh tables for each test

### Sample Test Models

#### User Model (Partition Key Only)
```python
class User(DynamoModel):
    class Meta:
        table_name = "test_users"

    email: str = Key()  # Partition key
    username: str
    age: int
    score: float = 0.0
    tags: list[str] = []
    active: bool = True
```

#### Message Model (Partition + Sort Key)
```python
class Message(DynamoModel):
    class Meta:
        table_name = "test_messages"

    room_id: str = Key()      # Partition key
    timestamp: str = SortKey()  # Sort key
    content: str
    user: str
    likes: int = 0
```

## Writing Tests

### Unit Test Example

```python
import pytest
from unittest.mock import patch

def test_save_calls_put_item(inject_mock_client, sample_user_model):
    """Test that save() calls put_item with correct data."""
    user = sample_user_model(email="test@example.com", username="test")

    user.save()

    # Verify put_item was called
    inject_mock_client.put_item.assert_called_once()
    call_args = inject_mock_client.put_item.call_args

    # Verify table name
    assert call_args[1]["TableName"] == "test_users"

    # Verify item data (DynamoDB format)
    item = call_args[1]["Item"]
    assert item["email"]["S"] == "test@example.com"
    assert item["username"]["S"] == "test"
```

### Integration Test Example

```python
@pytest.mark.integration
def test_save_and_get_user(clean_integration_tables, integration_user_model, sample_user_data):
    """Test saving a user and retrieving it."""
    # Create user instance
    user = integration_user_model(**sample_user_data)

    # Save to DynamoDB
    user.save()

    # Retrieve from DynamoDB
    retrieved = integration_user_model.get(sample_user_data["email"])

    assert retrieved is not None
    assert retrieved.email == sample_user_data["email"]
    assert retrieved.username == sample_user_data["username"]
```

## Coverage

### Coverage Configuration

Coverage is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
# ... other options
addopts = "--cov=dynantic --cov-report=html --cov-report=xml"
```

### Viewing Coverage

```bash
# Run tests with coverage
uv run pytest --cov=dynantic --cov-report=html

# View HTML report
open htmlcov/index.html
```

### Coverage Goals

- **Unit Tests**: 90%+ coverage of all code
- **Integration Tests**: Cover all major user-facing operations
- **Edge Cases**: Cover error conditions and edge cases

## Continuous Integration

### GitHub Actions

The project uses GitHub Actions for CI with the following jobs:

1. **Test** - Runs on multiple Python versions (3.9-3.13)
   - Unit tests (always)
   - Integration tests with LocalStack
   - Coverage reporting to Codecov

2. **Lint** - Code quality checks
   - mypy type checking
   - ruff linting and formatting

3. **Docs** - Documentation building (placeholder)

### Local CI Simulation

```bash
# Run full CI pipeline locally
uv run pytest tests/unit/ tests/integration/ --cov=dynantic
uv run mypy dynantic/ tests/
uv run ruff check dynantic/ tests/
uv run ruff format --check dynantic/ tests/
```

## Debugging Tests

### Common Issues

#### LocalStack Connection Issues

```bash
# Check LocalStack status
curl http://localhost:4566/_localstack/health

# Check LocalStack logs
docker compose logs localstack

# Restart LocalStack
docker compose restart localstack
```

#### Test Isolation

Each integration test gets fresh tables via the `clean_integration_tables` fixture. If tests interfere with each other, check:

1. Table names are unique per test
2. Fixtures properly clean up data
3. No shared state between tests

#### Mock Issues

For unit tests, ensure mocks are properly configured:

```python
# Good: Specific mock configuration
mock_client.get_item.return_value = {"Item": {"email": {"S": "test@example.com"}}}

# Bad: Generic mock that might not behave as expected
mock_client = MagicMock()  # May not handle all method calls correctly
```

### Debugging Commands

```bash
# Run specific test with debug output
pytest tests/unit/test_model_unit.py::TestDynamoModel::test_get_returns_model_instance -v -s

# Run tests with pdb on failure
pytest --pdb

# Run tests with detailed output
pytest -v --tb=long

# Run tests in parallel (if pytest-xdist installed)
pytest -n auto
```

## Best Practices

### Test Organization

1. **One concept per test**: Each test should verify one specific behavior
2. **Descriptive names**: Test names should clearly describe what they verify
3. **Arrange-Act-Assert**: Structure tests clearly
4. **DRY principle**: Use fixtures and helper functions to avoid duplication

### Mocking Guidelines

1. **Mock at the right level**: Mock boto3 clients, not internal methods
2. **Verify interactions**: Check that correct methods are called with correct arguments
3. **Don't mock everything**: Some integration tests should use real services

### Integration Test Guidelines

1. **Isolation**: Each test gets clean tables
2. **Realistic data**: Use realistic test data
3. **Performance**: Keep integration tests focused and not too numerous
4. **Cleanup**: Rely on fixtures for proper cleanup

### Coverage Guidelines

1. **Test public APIs**: Focus on testing public methods and behaviors
2. **Edge cases**: Test error conditions, boundaries, and unusual inputs
3. **Data variations**: Test with different data types and values
4. **Integration paths**: Test that components work together correctly

## Contributing

When adding new features:

1. **Add unit tests** for new functionality
2. **Add integration tests** for user-facing features
3. **Update fixtures** if new test models are needed
4. **Maintain coverage** above 90% for new code
5. **Update documentation** if testing patterns change

When fixing bugs:

1. **Add regression test** that reproduces the bug
2. **Verify fix** with the test
3. **Ensure no existing tests break**

## Troubleshooting

### Test Failures

**Unit tests failing**: Check mock configurations and test logic
**Integration tests failing**: Verify LocalStack is running and healthy
**Coverage low**: Add tests for uncovered code paths
**CI failing**: Check GitHub Actions logs for specific errors

### Performance Issues

**Slow tests**: Profile with `pytest --durations=10`
**Memory issues**: Check for large test data or memory leaks
**CI timeouts**: Optimize slow integration tests

### Dependency Issues

**Import errors**: Ensure all dependencies are installed
**Version conflicts**: Check Python and package versions
**Environment differences**: Test in clean environments

---

For more information, see the main project documentation or open an issue on GitHub.