# Transactions

**ACID transactions** across one or more DynamoDB tables. All operations succeed or all fail.

## Simple: transact_save

Atomically save multiple items — works across different tables.

```python
user = User(user_id="u1", name="Alice")
order = Order(order_id="o1", amount=99.99)
DynamoModel.transact_save([user, order])
```

## Advanced: transact_write

Combine Put, Delete, and ConditionCheck operations in a single transaction.

```python
from dynantic import Attr, TransactPut, TransactDelete, TransactConditionCheck

DynamoModel.transact_write([
    # Create-if-not-exists
    TransactPut(user, condition=Attr("user_id").not_exists()),
    # Delete with condition
    TransactDelete(Order, condition=Attr("status") == "cancelled", order_id="o1"),
    # Validate without modifying
    TransactConditionCheck(Account, Attr("balance") >= 100, account_id="acc-1"),
])
```

### Real-World Example: Money Transfer

```python
from dynantic import Attr, TransactPut

# Transfer $200 from Alice to Bob atomically
DynamoModel.transact_write([
    TransactPut(
        Account(account_id="acc-1", owner="Alice", balance=800.0),
        condition=(Attr("active") == True) & (Attr("balance") >= 200),
    ),
    TransactPut(
        Account(account_id="acc-2", owner="Bob", balance=700.0),
    ),
    TransactPut(transfer),
])
```

## Atomic Reads: transact_get

Get a consistent snapshot of multiple items.

```python
from dynantic import TransactGet

results = DynamoModel.transact_get([
    TransactGet(User, user_id="u1"),
    TransactGet(Order, order_id="o1"),
])
# results[0] is User | None, results[1] is Order | None
```

Missing items return `None` — no exceptions.

!!! warning "100-item limit"
    DynamoDB limits transactions to **100 items** per request. Dynantic validates this and raises `ValidationError` if exceeded.

## Transaction Types

| Type | Description |
|---|---|
| `TransactPut(model, condition=...)` | Save an item with optional condition |
| `TransactDelete(ModelClass, condition=..., **keys)` | Delete by key with optional condition |
| `TransactConditionCheck(ModelClass, condition, **keys)` | Validate condition without modifying |
| `TransactGet(ModelClass, **keys)` | Read an item atomically |
