# Installation

## Requirements

- **Python 3.10+**
- boto3 >= 1.34.0
- pydantic >= 2.6.0

## Install from PyPI

=== "pip"

    ```bash
    pip install dynantic
    ```

=== "uv"

    ```bash
    uv add dynantic
    ```

=== "poetry"

    ```bash
    poetry add dynantic
    ```

## Verify Installation

```python
import dynantic
print(dynantic.__version__)
```

## AWS Credentials

Dynantic uses **boto3** under the hood, so it follows the standard AWS credential resolution order:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. Shared credentials file (`~/.aws/credentials`)
3. AWS config file (`~/.aws/config`)
4. IAM role (on EC2, Lambda, ECS, etc.)

!!! tip "Lambda / ECS"
    On AWS Lambda or ECS, credentials are provided automatically via the execution role. No configuration needed.

For local development with [LocalStack](../integration/localstack.md), see the integration guide.
