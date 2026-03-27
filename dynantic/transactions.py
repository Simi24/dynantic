"""
Transaction support for Dynantic.

Provides ACID transactions across DynamoDB tables using
TransactWriteItems and TransactGetItems.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .conditions import Condition
    from .model import DynamoModel

TRANSACT_LIMIT = 100


class TransactPut:
    """Wraps a model instance for transactional put."""

    def __init__(self, item: DynamoModel, condition: Condition | None = None) -> None:
        self.item = item
        self.condition = condition

    def _to_transact_item(self) -> dict[str, Any]:
        config = self.item._meta
        serializer = self.item._serializer

        data = self.item.model_dump(mode="python", exclude_none=True)

        # Handle TTL conversion
        from .config import convert_ttl_fields

        convert_ttl_fields(data, config)

        dynamo_item = serializer.to_dynamo(data)

        put: dict[str, Any] = {
            "TableName": config.table_name,
            "Item": dynamo_item,
        }

        if self.condition is not None:
            from .conditions import compile_condition

            condition_params = compile_condition(self.condition, serializer)
            put.update(condition_params)

        return {"Put": put}


class TransactDelete:
    """Wraps a delete operation for transactional delete."""

    def __init__(
        self,
        model_cls: type[DynamoModel],
        condition: Condition | None = None,
        **key_values: Any,
    ) -> None:
        self.model_cls = model_cls
        self.key_values = key_values
        self.condition = condition

    def _to_transact_item(self) -> dict[str, Any]:
        config = self.model_cls._meta
        serializer = self.model_cls._serializer

        dynamo_key = serializer.to_dynamo(self.key_values)

        delete: dict[str, Any] = {
            "TableName": config.table_name,
            "Key": dynamo_key,
        }

        if self.condition is not None:
            from .conditions import compile_condition

            condition_params = compile_condition(self.condition, serializer)
            delete.update(condition_params)

        return {"Delete": delete}


class TransactConditionCheck:
    """Wraps a condition check for transactional validation."""

    def __init__(
        self,
        model_cls: type[DynamoModel],
        condition: Condition,
        **key_values: Any,
    ) -> None:
        self.model_cls = model_cls
        self.key_values = key_values
        self.condition = condition

    def _to_transact_item(self) -> dict[str, Any]:
        from .conditions import compile_condition

        config = self.model_cls._meta
        serializer = self.model_cls._serializer

        dynamo_key = serializer.to_dynamo(self.key_values)

        check: dict[str, Any] = {
            "TableName": config.table_name,
            "Key": dynamo_key,
        }

        condition_params = compile_condition(self.condition, serializer)
        check.update(condition_params)

        return {"ConditionCheck": check}


class TransactGet:
    """Wraps a get operation for transactional reads."""

    def __init__(self, model_cls: type[DynamoModel], **key_values: Any) -> None:
        self.model_cls = model_cls
        self.key_values = key_values

    def _to_transact_item(self) -> dict[str, Any]:
        config = self.model_cls._meta
        serializer = self.model_cls._serializer

        dynamo_key = serializer.to_dynamo(self.key_values)

        return {
            "Get": {
                "TableName": config.table_name,
                "Key": dynamo_key,
            }
        }


# Type alias for transact_write actions
TransactWriteAction = TransactPut | TransactDelete | TransactConditionCheck
