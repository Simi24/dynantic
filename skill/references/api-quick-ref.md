# Dynantic — API Quick Reference

## Imports

```python
from dynantic import (
    DynamoModel,       # Base model class
    Key,               # Partition key field (supports auto=True for UUID)
    SortKey,           # Sort key field (supports auto=True for UUID)
    GSIKey,            # GSI partition key field
    GSISortKey,        # GSI sort key field
    Discriminator,     # Polymorphism discriminator field
    TTL,               # TTL field (auto epoch conversion)
    Attr,              # Condition builder
    PageResult,        # Pagination result dataclass
    # Transactions
    TransactPut,             # Wraps item for transactional put
    TransactDelete,          # Wraps delete for transactional delete
    TransactConditionCheck,  # Asserts condition without modifying item
    TransactGet,             # Wraps get for transactional read
    # Update actions
    UpdateBuilder,     # Returned by .update() / .patch()
    Set, Add, Remove, Delete,  # Update action types
)

from dynantic.exceptions import (
    DynanticError,                         # Base exception
    ConditionalCheckFailedError,           # Condition failed
    TableNotFoundError,                    # Table doesn't exist
    ItemNotFoundError,                     # Item not found
    ProvisionedThroughputExceededError,    # Rate limited
    ItemCollectionSizeLimitError,          # Item collection > 10GB
    TransactionConflictError,              # Transaction conflict
    RequestTimeoutError,                   # Request timed out
    ValidationError,                       # Data validation failed
    DynamoSerializationError,              # Serialization failed
)
```

## DynamoModel Methods

### Class Methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `create` | `create(**kwargs)` | `T` (INSERT semantics, fails if PK exists) |
| `get` | `get(pk_value, sk_value=None)` | `T \| None` |
| `delete` | `delete(pk_value, sk_value=None, condition=None)` | `None` |
| `query` | `query(pk_value)` | `DynamoQueryBuilder[T]` |
| `query_index` | `query_index(index_name, pk_value)` | `DynamoQueryBuilder[T]` |
| `scan` | `scan(index_name=None)` | `DynamoScanBuilder[T]` |
| `update` | `update(pk_value, sk_value=None)` | `UpdateBuilder` |
| `batch_get` | `batch_get(keys)` | `list[T]` (auto-chunks at 100, retries) |
| `batch_save` | `batch_save(items)` | `None` (auto-chunks at 25, retries) |
| `batch_delete` | `batch_delete(keys)` | `None` (auto-chunks at 25, retries) |
| `batch_writer` | `batch_writer()` | `BatchWriter` context manager |
| `transact_save` | `transact_save(items)` | `None` (atomic, max 100) |
| `transact_write` | `transact_write(actions)` | `None` (atomic, max 100) |
| `transact_get` | `transact_get(actions)` | `list[T \| None]` (atomic, max 100) |
| `set_client` | `set_client(client)` | `None` |
| `using_client` | `using_client(client)` | Context manager |
| `register` | `@Model.register("VALUE")` | Decorator |

### Instance Methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `save` | `save(condition=None)` | `None` |
| `delete_item` | `delete_item(condition=None)` | `None` |
| `patch` | `patch()` | `UpdateBuilder` |

## BatchWriter Methods

Returned by `Model.batch_writer()`. Use as context manager.

| Method | Signature | Description |
|--------|-----------|-------------|
| `save` | `save(item)` | Add PutItem to batch |
| `delete` | `delete(**key_values)` | Add DeleteItem to batch |

Auto-flushes every 25 items. Flushes remaining on exit (only if no exception).

## Transaction Helper Classes

| Class | Constructor | Purpose |
|-------|-------------|---------|
| `TransactPut` | `TransactPut(item, condition=None)` | Put item in transaction |
| `TransactDelete` | `TransactDelete(ModelCls, condition=None, **key_values)` | Delete item in transaction |
| `TransactConditionCheck` | `TransactConditionCheck(ModelCls, condition, **key_values)` | Assert condition without write |
| `TransactGet` | `TransactGet(ModelCls, **key_values)` | Get item in transaction |

## Field Markers

| Marker | Usage | Notes |
|--------|-------|-------|
| `Key()` | `pk: str = Key()` | Partition key (exactly 1 required) |
| `Key(auto=True)` | `pk: UUID = Key(auto=True)` | Auto-generates UUID4 |
| `SortKey()` | `sk: str = SortKey()` | Sort key (0 or 1) |
| `SortKey(auto=True)` | `sk: UUID = SortKey(auto=True)` | Auto-generates UUID4 |
| `GSIKey(index_name=)` | `gsi: str = GSIKey(index_name="IX")` | GSI partition key |
| `GSISortKey(index_name=)` | `gsi_sk: str = GSISortKey(index_name="IX")` | GSI sort key |
| `Discriminator()` | `type: str = Discriminator()` | Polymorphism discriminator |
| `TTL()` | `expires: datetime = TTL()` | TTL field (datetime -> epoch auto) |

## DynamoQueryBuilder Methods

Chain these after `.query(pk)` or `.query_index(index, pk)`.

### Sort Key Conditions (pick one)

| Method | Expression |
|--------|-----------|
| `.eq(value)` | `SK = :val` |
| `.ne(value)` | `SK <> :val` |
| `.gt(value)` | `SK > :val` |
| `.ge(value)` | `SK >= :val` |
| `.lt(value)` | `SK < :val` |
| `.le(value)` | `SK <= :val` |
| `.between(low, high)` | `SK BETWEEN :lo AND :hi` |
| `.starts_with(prefix)` | `begins_with(SK, :prefix)` |

### Modifiers

| Method | Purpose |
|--------|---------|
| `.filter(condition)` | Post-query filter (chainable, AND) |
| `.limit(n)` | Max items to evaluate |
| `.reverse()` | Descending sort key order |
| `.using_index(name)` | Switch to a GSI |

### Terminal Methods

| Method | Returns |
|--------|---------|
| `.all()` | `list[T]` — all results, auto-paginates |
| `.first()` | `T \| None` — first match |
| `.one()` | `T` — exactly one match, raises otherwise |
| `.page(start_key=None)` | `PageResult[T]` — single page |
| `for item in builder:` | Lazy iteration |

## DynamoScanBuilder Methods

Same as query builder except no sort key conditions. Methods: `.filter()`, `.limit()`, `.using_index()`, `.all()`, `.first()`, `.one()`, `.page()`.

## UpdateBuilder Methods

Chain these after `.update(pk, sk)` or `.patch()`.

| Method | DynamoDB Action | Example |
|--------|----------------|---------|
| `.set(field, value)` | SET | `.set(User.name, "Alice")` |
| `.add(field, value)` | ADD | `.add(User.count, 1)` |
| `.remove(field)` | REMOVE | `.remove(User.temp)` |
| `.delete(field, value)` | DELETE (set) | `.delete(User.tags, {"old"})` |
| `.condition(cond)` | ConditionExpression | `.condition(Attr("v") == 1)` |
| `.return_values(mode)` | ReturnValues | `"ALL_NEW"`, `"NONE"`, etc. |
| `.execute()` | Send to DynamoDB | Returns dict or model |

## Attr Condition Methods

| Method | Expression |
|--------|-----------|
| `Attr(f) == v` / `.eq(v)` | `#f = :v` |
| `Attr(f) != v` / `.ne(v)` | `#f <> :v` |
| `Attr(f) > v` / `.gt(v)` | `#f > :v` |
| `Attr(f) >= v` / `.gte(v)` | `#f >= :v` |
| `Attr(f) < v` / `.lt(v)` | `#f < :v` |
| `Attr(f) <= v` / `.lte(v)` | `#f <= :v` |
| `.exists()` | `attribute_exists(#f)` |
| `.not_exists()` | `attribute_not_exists(#f)` |
| `.begins_with(prefix)` | `begins_with(#f, :p)` |
| `.contains(value)` | `contains(#f, :v)` |
| `.between(lo, hi)` | `#f BETWEEN :lo AND :hi` |
| `.is_in([values])` | `#f IN (:v1, :v2, ...)` |

### Logical Operators

| Operator | Meaning |
|----------|---------|
| `c1 & c2` | AND |
| `c1 \| c2` | OR |
| `~c` | NOT |

## PageResult[T]

| Field / Property | Type | Description |
|-----------------|------|-------------|
| `items` | `list[T]` | Items in this page |
| `last_evaluated_key` | `dict \| None` | Cursor for next page |
| `count` | `int` | Number of items |
| `has_more` | `bool` (property) | True if more pages exist |
