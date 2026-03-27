"""
Transaction Example

Demonstrates Dynantic's transaction API:
- transact_save: Simple multi-item atomic write
- transact_write: Advanced write with Put/Delete/ConditionCheck actions
- transact_get: Atomic multi-item read
"""

from dynantic import (
    Attr,
    DynamoModel,
    Key,
    TransactConditionCheck,
    TransactDelete,
    TransactGet,
    TransactPut,
)


class Account(DynamoModel):
    account_id: str = Key()
    owner: str
    balance: float
    active: bool = True

    class Meta:
        table_name = "accounts"


class Transfer(DynamoModel):
    transfer_id: str = Key()
    from_account: str
    to_account: str
    amount: float

    class Meta:
        table_name = "transfers"


# ── transact_save (simple) ──────────────────────────────────────────

# Atomically save multiple items — all succeed or all fail.
# Works across different tables.
alice = Account(account_id="acc-1", owner="Alice", balance=1000.0)
bob = Account(account_id="acc-2", owner="Bob", balance=500.0)
DynamoModel.transact_save([alice, bob])
print("Created 2 accounts atomically")


# ── transact_write (advanced) ───────────────────────────────────────

# Transfer $200 from Alice to Bob with safety checks.
# This single transaction:
#   1. Checks Alice is active and has enough funds
#   2. Updates Alice's balance (via Put with new state)
#   3. Updates Bob's balance (via Put with new state)
#   4. Records the transfer

transfer = Transfer(
    transfer_id="tx-001",
    from_account="acc-1",
    to_account="acc-2",
    amount=200.0,
)

DynamoModel.transact_write(
    [
        # Verify Alice is active before allowing the transfer
        TransactConditionCheck(
            Account,
            (Attr("active") == True) & (Attr("balance") >= 200),  # noqa: E712
            account_id="acc-1",
        ),
        # Write updated balances
        TransactPut(Account(account_id="acc-1", owner="Alice", balance=800.0)),
        TransactPut(Account(account_id="acc-2", owner="Bob", balance=700.0)),
        # Record the transfer
        TransactPut(transfer),
    ]
)
print("Transfer completed atomically")


# ── transact_write with conditional put ─────────────────────────────

# Create-if-not-exists: prevent duplicate accounts
charlie = Account(account_id="acc-3", owner="Charlie", balance=100.0)
DynamoModel.transact_write(
    [
        TransactPut(charlie, condition=Attr("account_id").not_exists()),
    ]
)
print("Created account only if it didn't exist")


# ── transact_write with delete ──────────────────────────────────────

# Close an account: delete it only if balance is zero
DynamoModel.transact_write(
    [
        TransactDelete(
            Account,
            condition=Attr("balance") == 0,
            account_id="acc-3",
        ),
    ]
)


# ── transact_get ────────────────────────────────────────────────────

# Read multiple items atomically — get a consistent snapshot.
results = DynamoModel.transact_get(
    [
        TransactGet(Account, account_id="acc-1"),
        TransactGet(Account, account_id="acc-2"),
        TransactGet(Transfer, transfer_id="tx-001"),
    ]
)

alice_account, bob_account, transfer_record = results

if alice_account:
    print(f"Alice: ${alice_account.balance}")
if bob_account:
    print(f"Bob: ${bob_account.balance}")
if transfer_record:
    print(f"Transfer: ${transfer_record.amount} from {transfer_record.from_account}")

# Missing items return None
results = DynamoModel.transact_get(
    [
        TransactGet(Account, account_id="acc-1"),
        TransactGet(Account, account_id="acc-nonexistent"),
    ]
)
print(f"Existing: {results[0] is not None}, Missing: {results[1] is None}")

# NOTE: DynamoDB limits transactions to 100 items per request.
# Dynantic validates this and raises ValidationError if exceeded.
