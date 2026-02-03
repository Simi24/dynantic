"""
Atomic update operations for Dynantic.

This module provides the classes and builders necessary to construct and execute
DynamoDB atomic updates (SET, REMOVE, ADD, DELETE) with Pydantic type validation.

Usage:
    User.update("pk", "sk") \\
        .set(User.status, "active") \\
        .add(User.login_count, 1) \\
        .execute()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ValidationError
from pydantic.type_adapter import TypeAdapter

from ._logging import logger, redact_key
from .conditions import Attr, DynCondition, compile_condition
from .exceptions import handle_dynamo_errors

if TYPE_CHECKING:
    from .base import DynamoModel


class UpdateAction(ABC):
    """Base class for all update actions."""

    def __init__(self, field: Attr | str, value: Any = None) -> None:
        self.field_name = field.name if isinstance(field, Attr) else field
        self.value = value

    @abstractmethod
    def validate(self, model_cls: type[DynamoModel]) -> Any:
        """
        Validates the value against the model field definition.
        Returns the validated value (which might be coerced).
        """
        pass

    def _get_field_info(self, model_cls: type[DynamoModel]) -> Any:
        """Helper to find the Pydantic field info for this attribute."""
        # This assumes a helper method exists on DynamoModel or we iterate
        for field_name, field in model_cls.model_fields.items():
            dynamo_name = field.alias or field_name
            if dynamo_name == self.field_name:
                return field

        # If strict validation is required, we could raise here.
        # For now, if field not found (dynamic schema?), return None -> no validation
        return None


class Set(UpdateAction):
    """
    Represents a SET action.
    User.update(...).set(User.name, "New Name")
    """

    def validate(self, model_cls: type[DynamoModel]) -> Any:
        # Special case: Set(field, None) -> Removed in compilation, so technically valid logic
        # but here we just return None.
        if self.value is None:
            return None

        field = self._get_field_info(model_cls)
        if field:
            # helper to validate value against field type
            # We construct a TypeAdapter for the field's annotation
            try:
                adapter = TypeAdapter(field.annotation)
                return adapter.validate_python(self.value)
            except ValidationError as e:
                raise ValueError(f"Validation failed for field '{self.field_name}': {e}") from e
        return self.value


class Remove(UpdateAction):
    """
    Represents a REMOVE action.
    User.update(...).remove(User.legacy_field)
    """

    def __init__(self, field: Attr | str) -> None:
        super().__init__(field, value=None)

    def validate(self, model_cls: type[DynamoModel]) -> Any:
        # Removal doesn't require value validation
        return None


class Add(UpdateAction):
    """
    Represents an ADD action (numbers or sets).
    User.update(...).add(User.count, 1)
    """

    def validate(self, model_cls: type[DynamoModel]) -> Any:
        field = self._get_field_info(model_cls)
        if field:
            # 1. Generic Pydantic Validation first
            try:
                adapter = TypeAdapter(field.annotation)
                validated_value = adapter.validate_python(self.value)
            except ValidationError as e:
                raise ValueError(f"Validation failed for field '{self.field_name}': {e}") from e

            # 2. Strict Check for ADD operations
            # ADD is only allowed for Numbers and Sets in DynamoDB
            # (and Pydantic handles int/float/Decimal conversion)
            is_number = isinstance(validated_value, (int, float, Decimal))
            is_set = isinstance(validated_value, (set, frozenset))

            if not (is_number or is_set):
                raise ValueError(
                    f"Invalid type for ADD operation on field '{self.field_name}'. "
                    f"DynamoDB ADD supports only Numbers and Sets. "
                    f"Got: {type(validated_value).__name__}"
                )

            return validated_value

        # Fallback if field not found (dynamic?) - checks strictly on value type
        # We can't know if the field in DB is compatible, but we can check the value being sent.
        if not isinstance(self.value, (int, float, Decimal, set, frozenset)):
            raise ValueError(
                f"Invalid value for ADD operation. "
                f"DynamoDB ADD supports only Numbers and Sets. "
                f"Got: {type(self.value).__name__}"
            )

        return self.value


class Delete(UpdateAction):
    """
    Represents a DELETE action (removing elements from a set).
    User.update(...).delete(User.tags, {"old_tag"})
    """

    def validate(self, model_cls: type[DynamoModel]) -> Any:
        field = self._get_field_info(model_cls)
        if field:
            # Expecting a set
            try:
                adapter = TypeAdapter(field.annotation)
                return adapter.validate_python(self.value)
            except ValidationError as e:
                raise ValueError(f"Validation failed for field '{self.field_name}': {e}") from e
        return self.value


class UpdateBuilder:
    """
    Fluent builder for correct DynamoDB UpdateExpressions.
    """

    def __init__(self, model_cls: type[DynamoModel], pk: Any, sk: Any | None = None) -> None:
        self.model_cls = model_cls
        self.pk = pk
        self.sk = sk
        self.actions: list[UpdateAction] = []
        self._condition: DynCondition | Any | None = None  # DynCondition or boto3 raw
        self._return_values: str = "NONE"

    def set(self, field: Any, value: Any) -> UpdateBuilder:
        """
        Set a field value.

        Usage:
            user.set(User.name, "New Name")
        """
        self.actions.append(Set(field, value))
        return self

    def remove(self, field: Attr | str) -> UpdateBuilder:
        """
        Remove a field.

        Usage:
            user.remove(User.legacy_field)
        """
        self.actions.append(Remove(field))
        return self

    def add(self, field: Attr | str, value: Any) -> UpdateBuilder:
        """
        Add a value to a field.

        Usage:
            user.add(User.count, 1)
        """
        self.actions.append(Add(field, value))
        return self

    def delete(self, field: Attr | str, value: Any) -> UpdateBuilder:
        """
        Delete a value from a field.

        Usage:
            user.delete(User.tags, {"old_tag"})
        """
        self.actions.append(Delete(field, value))
        return self

    def condition(self, condition: Any) -> UpdateBuilder:
        """
        Add a condition to the update.

        Usage:
            user.condition(User.age > 18)
        """
        self._condition = condition
        return self

    def return_values(
        self, return_values: Literal["NONE", "ALL_OLD", "UPDATED_OLD", "ALL_NEW", "UPDATED_NEW"]
    ) -> UpdateBuilder:
        """
        Set the return values.

        Usage:
            user.return_values("ALL_NEW")
        """
        self._return_values = return_values
        return self

    def _compile(self) -> dict[str, Any]:
        """
        Compiles the actions into DynamoDB parameters:
        UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues.
        Also merges the ConditionExpression if present.
        """
        if not self.actions:
            raise ValueError("No update actions specified")

        # 1. Group actions
        set_actions: list[Set] = []
        remove_actions: list[Remove] = []
        add_actions: list[Add] = []
        delete_actions: list[Delete] = []

        for action in self.actions:
            # Pydantic Validation
            validated_value = action.validate(self.model_cls)

            # Helper: Handle Set(None) -> Remove
            if isinstance(action, Set) and validated_value is None:
                remove_actions.append(Remove(action.field_name))
                continue

            # Update value in action to validated one
            action.value = validated_value

            if isinstance(action, Set):
                set_actions.append(action)
            elif isinstance(action, Remove):
                remove_actions.append(action)
            elif isinstance(action, Add):
                add_actions.append(action)
            elif isinstance(action, Delete):
                delete_actions.append(action)

        # 2. Build Expression
        parts = []
        names: dict[str, str] = {}
        values: dict[str, Any] = {}

        # We use simple counters to generate unique placeholders for this update context
        # Prefix 'u' to avoid collision with condition placeholders
        name_counter = 0
        value_counter = 0

        def get_name_ph(name: str) -> str:
            nonlocal name_counter
            # Check if name already mapped?
            # Boto3 simple builder doesn't dedup names usually, but we can if we want.
            # Let's just generate new ones for safety and simplicity.
            ph = f"#u_n{name_counter}"
            names[ph] = name
            name_counter += 1
            return ph

        def get_value_ph(val: Any) -> str:
            nonlocal value_counter
            ph = f":u_v{value_counter}"
            # Serialize for DynamoDB!
            # We access the serializer via the model class
            values[ph] = self.model_cls._serializer.to_dynamo_value(val)
            value_counter += 1
            return ph

        if set_actions:
            clauses = []
            for sa in set_actions:
                n = get_name_ph(sa.field_name)
                v = get_value_ph(sa.value)
                clauses.append(f"{n} = {v}")
            parts.append("SET " + ", ".join(clauses))

        if remove_actions:
            clauses = []
            for ra in remove_actions:
                n = get_name_ph(ra.field_name)
                clauses.append(n)
            parts.append("REMOVE " + ", ".join(clauses))

        if add_actions:
            clauses = []
            for aa in add_actions:
                n = get_name_ph(aa.field_name)
                v = get_value_ph(aa.value)
                clauses.append(f"{n} {v}")
            parts.append("ADD " + ", ".join(clauses))

        if delete_actions:
            clauses = []
            for da in delete_actions:
                n = get_name_ph(da.field_name)
                v = get_value_ph(da.value)
                clauses.append(f"{n} {v}")
            parts.append("DELETE " + ", ".join(clauses))

        update_expression = " ".join(parts)

        result: dict[str, Any] = {"UpdateExpression": update_expression}

        # 3. Merge Condition if present
        if self._condition:
            cond_params = compile_condition(self._condition, self.model_cls._serializer)
            result["ConditionExpression"] = cond_params["ConditionExpression"]

            # Merge Names
            if "ExpressionAttributeNames" in cond_params:
                # We need to make sure we don't overwrite user's condition names if they collide?
                # Using prefixes #u_ should prevent collision with boto3 generated ones (#n0, etc)
                names.update(cond_params["ExpressionAttributeNames"])

            # Merge Values
            if "ExpressionAttributeValues" in cond_params:
                values.update(cond_params["ExpressionAttributeValues"])

        if names:
            result["ExpressionAttributeNames"] = names
        if values:
            result["ExpressionAttributeValues"] = values

        return result

    def execute(self) -> Any:
        # Build Key
        key_dict = {self.model_cls._meta.pk_name: self.pk}
        if self.sk and self.model_cls._meta.sk_name:
            key_dict[self.model_cls._meta.sk_name] = self.sk

        dynamo_key = self.model_cls._serializer.to_dynamo(key_dict)

        params = self._compile()
        params["TableName"] = self.model_cls._meta.table_name
        params["Key"] = dynamo_key
        params["ReturnValues"] = self._return_values

        client = self.model_cls._get_client()

        # We need to handle known dynamo errors?
        # The base.py usually uses a context manager.
        # But we are in a different module.
        # We should import handle_dynamo_errors from exceptions

        logger.info(
            "Executing atomic update",
            extra={
                "table": self.model_cls._meta.table_name,
                "key_hash": redact_key(key_dict),
                "operation": "update",
                "action_count": len(self.actions),
                "has_condition": self._condition is not None,
            },
        )

        if self._condition:
            logger.debug(
                "Update condition details",
                extra={
                    "table": self.model_cls._meta.table_name,
                    "operation": "update",
                    "condition_expression": params.get("ConditionExpression"),
                },
            )

        with handle_dynamo_errors(table_name=self.model_cls._meta.table_name):
            response = client.update_item(**params)
            logger.info(
                "Update successful",
                extra={"table": self.model_cls._meta.table_name, "operation": "update"},
            )

        if self._return_values == "ALL_NEW" and "Attributes" in response:
            raw_data = self.model_cls._serializer.from_dynamo(response["Attributes"])
            return self.model_cls._deserialize_item(raw_data)

        return response
