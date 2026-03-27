"""Integration tests for transaction support (transact_save, transact_write, transact_get)."""

import pytest

from dynantic import (
    Attr,
    DynamoModel,
    TransactConditionCheck,
    TransactDelete,
    TransactGet,
    TransactionConflictError,
    TransactPut,
)


@pytest.mark.integration
class TestTransactSave:
    def test_transact_save_single_table(
        self, clean_integration_tables, integration_user_model
    ):
        """transact_save writes multiple items to the same table atomically."""
        users = [
            integration_user_model(email=f"ts{i}@test.com", username=f"user{i}", age=20 + i)
            for i in range(3)
        ]
        DynamoModel.transact_save(users)

        for i in range(3):
            retrieved = integration_user_model.get(f"ts{i}@test.com")
            assert retrieved is not None
            assert retrieved.username == f"user{i}"

    def test_transact_save_cross_table(
        self, clean_integration_tables, integration_user_model, integration_message_model
    ):
        """transact_save writes items to different tables atomically."""
        user = integration_user_model(email="cross@test.com", username="cross", age=30)
        msg = integration_message_model(
            room_id="general", timestamp="2023-01-01T10:00:00Z",
            content="Hello!", user="cross",
        )

        DynamoModel.transact_save([user, msg])

        assert integration_user_model.get("cross@test.com") is not None
        results = list(integration_message_model.query("general"))
        assert len(results) == 1
        assert results[0].content == "Hello!"

    def test_transact_save_overwrites_existing(
        self, clean_integration_tables, integration_user_model
    ):
        """transact_save overwrites existing items (Put semantics)."""
        integration_user_model(email="ow@test.com", username="old", age=25).save()

        updated = integration_user_model(email="ow@test.com", username="new", age=30)
        DynamoModel.transact_save([updated])

        retrieved = integration_user_model.get("ow@test.com")
        assert retrieved.username == "new"
        assert retrieved.age == 30


@pytest.mark.integration
class TestTransactWrite:
    def test_transact_put(
        self, clean_integration_tables, integration_user_model
    ):
        """TransactPut creates items."""
        user = integration_user_model(email="tp@test.com", username="alice", age=28)
        DynamoModel.transact_write([TransactPut(user)])

        retrieved = integration_user_model.get("tp@test.com")
        assert retrieved is not None
        assert retrieved.username == "alice"

    def test_transact_delete(
        self, clean_integration_tables, integration_user_model
    ):
        """TransactDelete removes items."""
        integration_user_model(email="td@test.com", username="bob", age=30).save()
        assert integration_user_model.get("td@test.com") is not None

        DynamoModel.transact_write([
            TransactDelete(integration_user_model, email="td@test.com"),
        ])

        assert integration_user_model.get("td@test.com") is None

    def test_transact_put_with_condition(
        self, clean_integration_tables, integration_user_model
    ):
        """TransactPut with condition creates only if item doesn't exist."""
        user = integration_user_model(email="cond@test.com", username="first", age=25)
        DynamoModel.transact_write([
            TransactPut(user, condition=Attr("email").not_exists()),
        ])

        assert integration_user_model.get("cond@test.com").username == "first"

        # Second write with same condition should fail
        user2 = integration_user_model(email="cond@test.com", username="second", age=30)
        with pytest.raises(TransactionConflictError):
            DynamoModel.transact_write([
                TransactPut(user2, condition=Attr("email").not_exists()),
            ])

        # Original item unchanged
        assert integration_user_model.get("cond@test.com").username == "first"

    def test_transact_delete_with_condition(
        self, clean_integration_tables, integration_user_model
    ):
        """TransactDelete with condition deletes only if condition is met."""
        integration_user_model(
            email="cd@test.com", username="charlie", age=25, active=True
        ).save()

        # Delete with wrong condition should fail
        with pytest.raises(TransactionConflictError):
            DynamoModel.transact_write([
                TransactDelete(
                    integration_user_model,
                    condition=Attr("active") == False,  # noqa: E712
                    email="cd@test.com",
                ),
            ])

        # Item still exists
        assert integration_user_model.get("cd@test.com") is not None

        # Delete with correct condition
        DynamoModel.transact_write([
            TransactDelete(
                integration_user_model,
                condition=Attr("active") == True,  # noqa: E712
                email="cd@test.com",
            ),
        ])
        assert integration_user_model.get("cd@test.com") is None

    def test_transact_condition_check(
        self, clean_integration_tables, integration_user_model
    ):
        """TransactConditionCheck validates without modifying the item."""
        integration_user_model(
            email="cc@test.com", username="diana", age=25, active=True
        ).save()

        new_user = integration_user_model(email="cc2@test.com", username="eve", age=22)

        # Put new user only if existing user is active (condition check)
        DynamoModel.transact_write([
            TransactConditionCheck(
                integration_user_model,
                Attr("active") == True,  # noqa: E712
                email="cc@test.com",
            ),
            TransactPut(new_user),
        ])

        # Both items exist
        assert integration_user_model.get("cc@test.com") is not None
        assert integration_user_model.get("cc2@test.com") is not None

    def test_transact_condition_check_fails(
        self, clean_integration_tables, integration_user_model
    ):
        """Failing ConditionCheck cancels the entire transaction."""
        integration_user_model(
            email="fail@test.com", username="frank", age=25, active=False
        ).save()

        new_user = integration_user_model(email="fail2@test.com", username="grace", age=22)

        with pytest.raises(TransactionConflictError):
            DynamoModel.transact_write([
                TransactConditionCheck(
                    integration_user_model,
                    Attr("active") == True,  # noqa: E712
                    email="fail@test.com",
                ),
                TransactPut(new_user),
            ])

        # Neither change happened — original unchanged, new not created
        assert integration_user_model.get("fail@test.com").username == "frank"
        assert integration_user_model.get("fail2@test.com") is None

    def test_transact_write_mixed_actions(
        self, clean_integration_tables, integration_user_model
    ):
        """Mixed Put + Delete + ConditionCheck in a single transaction."""
        integration_user_model(
            email="mix1@test.com", username="alice", age=25, active=True
        ).save()
        integration_user_model(
            email="mix2@test.com", username="bob", age=30
        ).save()

        new_user = integration_user_model(email="mix3@test.com", username="charlie", age=28)

        DynamoModel.transact_write([
            TransactConditionCheck(
                integration_user_model,
                Attr("active") == True,  # noqa: E712
                email="mix1@test.com",
            ),
            TransactDelete(integration_user_model, email="mix2@test.com"),
            TransactPut(new_user),
        ])

        assert integration_user_model.get("mix1@test.com") is not None  # Unchanged
        assert integration_user_model.get("mix2@test.com") is None  # Deleted
        assert integration_user_model.get("mix3@test.com") is not None  # Created


@pytest.mark.integration
class TestTransactGet:
    def test_transact_get_multiple_items(
        self, clean_integration_tables, integration_user_model
    ):
        """transact_get retrieves multiple items atomically."""
        for i in range(3):
            integration_user_model(
                email=f"tg{i}@test.com", username=f"user{i}", age=20 + i
            ).save()

        results = DynamoModel.transact_get([
            TransactGet(integration_user_model, email=f"tg{i}@test.com")
            for i in range(3)
        ])

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result is not None
            assert result.email == f"tg{i}@test.com"
            assert result.username == f"user{i}"

    def test_transact_get_cross_table(
        self, clean_integration_tables, integration_user_model, integration_message_model
    ):
        """transact_get retrieves items from different tables."""
        integration_user_model(email="xtg@test.com", username="alice", age=25).save()
        integration_message_model(
            room_id="room1", timestamp="2023-01-01T10:00:00Z",
            content="Hello!", user="alice",
        ).save()

        results = DynamoModel.transact_get([
            TransactGet(integration_user_model, email="xtg@test.com"),
            TransactGet(
                integration_message_model,
                room_id="room1", timestamp="2023-01-01T10:00:00Z",
            ),
        ])

        assert len(results) == 2
        assert results[0].email == "xtg@test.com"
        assert results[1].content == "Hello!"

    def test_transact_get_missing_item(
        self, clean_integration_tables, integration_user_model
    ):
        """transact_get returns None for items that don't exist."""
        integration_user_model(email="exists@test.com", username="real", age=25).save()

        results = DynamoModel.transact_get([
            TransactGet(integration_user_model, email="exists@test.com"),
            TransactGet(integration_user_model, email="missing@test.com"),
        ])

        assert len(results) == 2
        assert results[0] is not None
        assert results[0].email == "exists@test.com"
        assert results[1] is None

    def test_transact_get_preserves_types(
        self, clean_integration_tables, integration_user_model
    ):
        """transact_get preserves field types correctly."""
        integration_user_model(
            email="types@test.com", username="typed", age=42,
            score=98.5, tags=["a", "b"], active=True,
        ).save()

        results = DynamoModel.transact_get([
            TransactGet(integration_user_model, email="types@test.com"),
        ])

        user = results[0]
        assert isinstance(user.age, int)
        assert isinstance(user.score, float)
        assert isinstance(user.tags, list)
        assert isinstance(user.active, bool)
        assert user.age == 42
        assert user.score == 98.5
        assert user.tags == ["a", "b"]
