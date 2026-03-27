# Dynantic Examples

Examples demonstrating core features of the Dynantic library.

## Examples

### [model.py](./model.py)
AWS Movies table example following the [official DynamoDB Getting Started guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GettingStartedDynamoDB.html).

**Demonstrates:**
- Composite keys (partition key + sort key)
- CRUD operations
- Querying with sort key conditions
- Atomic updates
- Conditional writes

### [single_table_design.py](./single_table_design.py)
Single table design pattern using polymorphic models.

**Demonstrates:**
- Polymorphic models with `Discriminator`
- `@register` decorator
- Multiple entity types in one table (Customer, Order, Product)
- Efficient access patterns

### [gsi_examples.py](./gsi_examples.py)
Global Secondary Index demonstrations.

**Demonstrates:**
- Multiple GSIs on one model
- `GSIKey` and `GSISortKey` fields
- Querying different indexes
- Range queries on GSI sort keys

### [batch_operations.py](./batch_operations.py)
Batch read/write operations with auto-chunking.

**Demonstrates:**
- `batch_save` — write multiple items (auto-chunked at 25)
- `batch_get` — read multiple items by key (auto-chunked at 100)
- `batch_delete` — delete multiple items by key
- `batch_writer` — context manager for mixed put/delete with auto-flush
- Automatic exponential backoff retry for unprocessed items

### [transactions.py](./transactions.py)
ACID transactions across DynamoDB tables.

**Demonstrates:**
- `transact_save` — simple atomic multi-item write
- `transact_write` — advanced write with `TransactPut`, `TransactDelete`, `TransactConditionCheck`
- `transact_get` — atomic multi-item read
- Cross-table transactions
- Conditional transaction actions

### [ttl_example.py](./ttl_example.py)
TTL (Time To Live) field support.

**Demonstrates:**
- `TTL()` field marker for datetime and int types
- Automatic datetime-to-epoch conversion on save
- Automatic epoch-to-datetime conversion on read
- TTL across all write paths (save, batch, transactions)

### [auto_uuid.py](./auto_uuid.py)
Auto-UUID generation and INSERT-safe create().

**Demonstrates:**
- `Key(auto=True)` / `SortKey(auto=True)` for auto-generated UUID4 keys
- `create()` method with INSERT semantics (`Attr(pk).not_exists()`)
- Explicit PK override
- `save()` as upsert after `create()`
- `batch_save` with auto-UUID models

### [fastapi_integration/main.py](./fastapi_integration/main.py)
Minimal FastAPI application.

**Demonstrates:**
- Using Dynantic models as FastAPI response models
- CRUD endpoints
- Automatic OpenAPI documentation

**Run:**
```bash
cd fastapi_integration
pip install -r requirements.txt
uvicorn main:app --reload
# Visit http://localhost:8000/docs
```

## Notes

- Examples are educational code snippets, not production applications
- You'll need to create DynamoDB tables before running
- Use AWS credentials or LocalStack for testing
