"""
Conditional writes DSL for Dynantic.

This module provides a DynCondition wrapper and Attr builder that create
condition expressions compatible with DynamoDB's ConditionExpression.
It delegates expression building to boto3's internal ConditionExpressionBuilder
while keeping boto3 internals hidden from the public API.

Design:
- DynCondition wraps boto3 ConditionBase, stored in .raw attribute
- Attr builder wraps boto3 Attr internally, returns DynCondition
- Operators &, |, ~ on DynCondition produce new DynCondition instances
- At compilation time, DynCondition.raw is fed to boto3's builder

Usage:
    from dynantic import Attr

    # Simple conditions
    user.save(condition=Attr("email").not_exists())
    user.save(condition=Attr("version") == 1)

    # Composed conditions
    condition = (Attr("age") >= 18) & (Attr("status") == "active")
    user.save(condition=condition)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from boto3.dynamodb.conditions import And as Boto3And
from boto3.dynamodb.conditions import Attr as Boto3Attr
from boto3.dynamodb.conditions import ConditionBase as Boto3ConditionBase
from boto3.dynamodb.conditions import Not as Boto3Not
from boto3.dynamodb.conditions import Or as Boto3Or

if TYPE_CHECKING:
    from .serializer import DynamoSerializer

# Type alias for condition parameter (DynCondition or raw boto3 for passthrough)
Condition = Union["DynCondition", Boto3ConditionBase]


class DynCondition:
    """
    Dynantic-owned wrapper for DynamoDB condition expressions.

    This class wraps a boto3 condition object (stored in .raw) and provides
    Python operators for composing conditions. It keeps boto3 internals
    hidden from the public API while delegating expression correctness
    to boto3.

    Users typically don't instantiate this directly - use Attr() instead.

    Attributes:
        raw: The underlying boto3 ConditionBase object (internal use)
    """

    __slots__ = ("raw",)

    def __init__(self, raw: Boto3ConditionBase) -> None:
        """
        Initialize with a boto3 condition object.

        Args:
            raw: The underlying boto3 condition (internal)
        """
        self.raw = raw

    def __and__(self, other: Condition) -> DynCondition:
        """
        Combine conditions with AND.

        Usage:
            condition = (Attr("age") >= 18) & (Attr("active") == True)
        """
        other_raw = _extract_raw(other)
        return DynCondition(Boto3And(self.raw, other_raw))

    def __rand__(self, other: Condition) -> DynCondition:
        """Support for: boto3_condition & DynCondition"""
        other_raw = _extract_raw(other)
        return DynCondition(Boto3And(other_raw, self.raw))

    def __or__(self, other: Condition) -> DynCondition:
        """
        Combine conditions with OR.

        Usage:
            condition = (Attr("role") == "admin") | (Attr("role") == "moderator")
        """
        other_raw = _extract_raw(other)
        return DynCondition(Boto3Or(self.raw, other_raw))

    def __ror__(self, other: Condition) -> DynCondition:
        """Support for: boto3_condition | DynCondition"""
        other_raw = _extract_raw(other)
        return DynCondition(Boto3Or(other_raw, self.raw))

    def __invert__(self) -> DynCondition:
        """
        Negate a condition with NOT.

        Usage:
            condition = ~Attr("deleted").exists()
        """
        return DynCondition(Boto3Not(self.raw))

    def __repr__(self) -> str:
        return f"DynCondition({self.raw!r})"


class Attr:
    """
    Represents a DynamoDB attribute for building conditions.

    This class wraps boto3.dynamodb.conditions.Attr internally and provides
    a clean API for building condition expressions. All methods return
    DynCondition instances (not raw boto3 objects).

    Usage:
        # Comparison operators
        Attr("age") >= 18
        Attr("status") == "active"
        Attr("score") < 100

        # DynamoDB functions
        Attr("email").not_exists()  # For create-if-not-exists
        Attr("name").begins_with("A")
        Attr("tags").contains("premium")
        Attr("age").between(18, 65)
        Attr("status").is_in(["active", "pending"])
    """

    __slots__ = ("name", "_boto3_attr")

    def __init__(self, name: str) -> None:
        """
        Initialize an attribute reference.

        Args:
            name: The attribute name in DynamoDB
        """
        self.name = name
        self._boto3_attr = Boto3Attr(name)

    # Comparison Operators - all return DynCondition

    def __eq__(self, value: Any) -> DynCondition:  # type: ignore[override]
        """Equals condition: Attr("field") == value"""
        return DynCondition(self._boto3_attr.eq(value))

    def __ne__(self, value: Any) -> DynCondition:  # type: ignore[override]
        """Not equals condition: Attr("field") != value"""
        return DynCondition(self._boto3_attr.ne(value))

    def __lt__(self, value: Any) -> DynCondition:
        """Less than condition: Attr("field") < value"""
        return DynCondition(self._boto3_attr.lt(value))

    def __le__(self, value: Any) -> DynCondition:
        """Less than or equal condition: Attr("field") <= value"""
        return DynCondition(self._boto3_attr.lte(value))

    def __gt__(self, value: Any) -> DynCondition:
        """Greater than condition: Attr("field") > value"""
        return DynCondition(self._boto3_attr.gt(value))

    def __ge__(self, value: Any) -> DynCondition:
        """Greater than or equal condition: Attr("field") >= value"""
        return DynCondition(self._boto3_attr.gte(value))

    # DynamoDB Function Methods - all return DynCondition

    def exists(self) -> DynCondition:
        """
        Checks if the attribute exists.

        Usage:
            Attr("optional_field").exists()
        """
        return DynCondition(self._boto3_attr.exists())

    def not_exists(self) -> DynCondition:
        """
        Checks if the attribute does NOT exist.

        Common use case: Create-if-not-exists pattern

        Usage:
            user.save(condition=Attr("email").not_exists())
        """
        return DynCondition(self._boto3_attr.not_exists())

    def begins_with(self, prefix: str) -> DynCondition:
        """
        Checks if string attribute begins with prefix.

        Usage:
            Attr("name").begins_with("John")
        """
        return DynCondition(self._boto3_attr.begins_with(prefix))

    def contains(self, value: Any) -> DynCondition:
        """
        Checks if attribute contains value.

        For strings: substring match
        For lists/sets: membership check

        Usage:
            Attr("email").contains("@gmail.com")
            Attr("tags").contains("premium")
        """
        return DynCondition(self._boto3_attr.contains(value))

    def between(self, low: Any, high: Any) -> DynCondition:
        """
        Checks if attribute is between low and high (inclusive).

        Usage:
            Attr("age").between(18, 65)
        """
        return DynCondition(self._boto3_attr.between(low, high))

    def is_in(self, values: list[Any]) -> DynCondition:
        """
        Checks if attribute value is in the provided list.

        Usage:
            Attr("status").is_in(["active", "pending", "review"])
        """
        return DynCondition(self._boto3_attr.is_in(values))

    def __repr__(self) -> str:
        return f"Attr({self.name!r})"


def _extract_raw(condition: Condition) -> Boto3ConditionBase:
    """
    Extracts the boto3 condition from either DynCondition or raw boto3 condition.

    This enables passthrough support: users can pass raw boto3 conditions
    which we wrap internally.

    Args:
        condition: DynCondition or raw boto3 ConditionBase

    Returns:
        The underlying boto3 ConditionBase

    Raises:
        TypeError: If condition is neither DynCondition nor boto3 ConditionBase
    """
    if isinstance(condition, DynCondition):
        return condition.raw
    elif isinstance(condition, Boto3ConditionBase):
        return condition
    else:
        raise TypeError(
            f"Expected DynCondition or boto3 ConditionBase, got {type(condition).__name__}"
        )


def wrap_condition(condition: Condition) -> DynCondition:
    """
    Ensures a condition is wrapped in DynCondition.

    If already a DynCondition, returns as-is.
    If a raw boto3 condition, wraps it in DynCondition.

    Args:
        condition: DynCondition or raw boto3 ConditionBase

    Returns:
        DynCondition wrapping the condition
    """
    if isinstance(condition, DynCondition):
        return condition
    elif isinstance(condition, Boto3ConditionBase):
        return DynCondition(condition)
    else:
        raise TypeError(
            f"Expected DynCondition or boto3 ConditionBase, got {type(condition).__name__}"
        )


def compile_condition(
    condition: Condition,
    serializer: DynamoSerializer,
) -> dict[str, Any]:
    """
    Compiles a condition into DynamoDB request parameters.

    Uses boto3's ConditionExpressionBuilder to generate:
    - ConditionExpression (string)
    - ExpressionAttributeNames (dict)
    - ExpressionAttributeValues (dict)

    This function is the integration point between Dynantic's DSL
    and the low-level DynamoDB API. It extracts the raw boto3 condition
    and delegates to boto3's builder for expression correctness.

    Args:
        condition: A DynCondition or raw boto3 condition object
        serializer: DynamoSerializer for converting values to DynamoDB format

    Returns:
        Dict with ConditionExpression, and optionally ExpressionAttributeNames
        and ExpressionAttributeValues (only included if non-empty)
    """
    from boto3.dynamodb.conditions import ConditionExpressionBuilder

    # Extract the raw boto3 condition (handles both DynCondition and passthrough)
    boto3_condition = _extract_raw(condition)

    # Use boto3's builder to compile the expression
    # This handles reserved keywords, placeholder generation, etc.
    builder = ConditionExpressionBuilder()
    expression = builder.build_expression(boto3_condition, is_key_condition=False)

    # Build the result dict
    result: dict[str, Any] = {
        "ConditionExpression": expression.condition_expression,
    }

    # Add attribute names if any (for reserved keywords like "name", "status")
    if expression.attribute_name_placeholders:
        result["ExpressionAttributeNames"] = dict(expression.attribute_name_placeholders)

    # Add attribute values, serialized for low-level DynamoDB API
    if expression.attribute_value_placeholders:
        # boto3's builder uses placeholder names like :n0, :n1, etc.
        # Values need to be serialized to DynamoDB format ({"S": "..."}, {"N": "..."}, etc.)
        serialized_values = {}
        for placeholder, value in expression.attribute_value_placeholders.items():
            serialized_values[placeholder] = serializer.to_dynamo_value(value)
        result["ExpressionAttributeValues"] = serialized_values

    return result
