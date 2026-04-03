# Comparison with Alternatives

## Feature Matrix

| Feature | **Dynantic** | **PynamoDB** | **Raw boto3** |
|---|:---:|:---:|:---:|
| Type Safety | Pydantic v2 | Custom types | Dict-based |
| IDE Autocomplete | Excellent | Good | Limited |
| Query DSL | Pythonic | Pythonic | Dict-based |
| Batch Operations | Yes | Yes | Yes |
| Transactions | Yes | Yes | Yes |
| TTL Support | Auto-convert | Yes | Manual |
| Polymorphism | Yes | No | No |
| Auto-UUID | Yes | No | No |
| Async Support | No (use threadpool) | No | No (use aioboto3) |
| Maturity | Beta | Stable | AWS Official |

## When to Use Dynantic

- You use **Pydantic** and want DynamoDB integration
- You're building **Lambda functions** or sync applications
- You want **IDE autocomplete** with Pydantic validation
- You need **single-table design** with polymorphism
- You value **developer experience** and clean DSL

## When to Use PynamoDB

- You want a **mature, battle-tested** library
- You prefer a custom type system over Pydantic
- You don't need Pydantic's validation features

## When to Use Raw boto3

- You need **maximum control** and flexibility
- You have simple use cases with few models
- You want AWS's official SDK with guaranteed compatibility

## When to Use aioboto3

- You need **native async/await** support
- You're building async applications (aiohttp, FastAPI with async endpoints)
- You're willing to manage async client lifecycle

## Limitations

| Feature | Status | Notes |
|---|---|---|
| Async support | Not planned | Use `asyncio.to_thread()` or aioboto3 |
| Streams | Not planned | Use AWS Lambda triggers |
| PartiQL | Not planned | Use standard query API |
| Auto-migrations | Not planned | Manage tables with IaC (Terraform, CDK) |

### Design Constraints

- **No relationships** — DynamoDB doesn't support joins
- **No schema enforcement** — DynamoDB is schemaless (Pydantic validates on read/write)
- **Cursor opacity** — Pagination cursors are plain dicts (not cryptographically signed)
