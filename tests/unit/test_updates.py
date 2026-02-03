import pytest

from dynantic.base import DynamoModel
from dynantic.fields import Key


# Mock Model for testing
class User(DynamoModel):
    class Meta:
        table_name = "users"
        region = "us-east-1"  # Optional, but good for completeness

    email: str = Key()
    name: str | None = None
    age: int | None = None
    tags: set[str] | None = None
    score: float | None = None


def test_update_builder_init():
    builder = User.update("test@example.com")
    assert builder.pk == "test@example.com"
    assert builder.model_cls == User
    assert builder.actions == []


def test_set_action_compilation():
    builder = User.update("test@example.com").set(User.name, "Alice")
    params = builder._compile()

    assert params["UpdateExpression"] == "SET #u_n0 = :u_v0"
    assert params["ExpressionAttributeNames"] == {"#u_n0": "name"}
    assert params["ExpressionAttributeValues"] == {":u_v0": {"S": "Alice"}}


def test_multiple_set_actions():
    builder = User.update("test@example.com").set(User.name, "Alice").set(User.age, 30)

    params = builder._compile()

    # Order isn't guaranteed for keys in dict, but list order in expression is preserved based on action order
    # The actions are grouped by type. Both are SET.
    # Implementation iterates set_actions.

    assert "SET #u_n0 = :u_v0, #u_n1 = :u_v1" in params["UpdateExpression"]

    names = params["ExpressionAttributeNames"]
    values = params["ExpressionAttributeValues"]

    # Verify mappings exist
    assert list(names.values()) == ["name", "age"] or list(names.values()) == ["age", "name"]
    # We can't strictly assert placeholder numbering without knowing internal counter state if shared,
    # but for a fresh builder it should be stable.

    assert names["#u_n0"] == "name"
    assert values[":u_v0"]["S"] == "Alice"
    assert names["#u_n1"] == "age"
    assert values[":u_v1"]["N"] == "30"


def test_remove_action():
    builder = User.update("pk").remove(User.age)
    params = builder._compile()
    assert params["UpdateExpression"] == "REMOVE #u_n0"
    assert params["ExpressionAttributeNames"] == {"#u_n0": "age"}
    # No values for remove
    assert "ExpressionAttributeValues" not in params


def test_add_action():
    builder = User.update("pk").add(User.age, 1)
    params = builder._compile()
    assert params["UpdateExpression"] == "ADD #u_n0 :u_v0"
    assert params["ExpressionAttributeNames"] == {"#u_n0": "age"}
    assert params["ExpressionAttributeValues"] == {":u_v0": {"N": "1"}}


def test_delete_from_set():
    builder = User.update("pk").delete(User.tags, {"old"})
    params = builder._compile()
    assert params["UpdateExpression"] == "DELETE #u_n0 :u_v0"
    assert params["ExpressionAttributeNames"] == {"#u_n0": "tags"}
    assert params["ExpressionAttributeValues"] == {":u_v0": {"SS": ["old"]}}


def test_mixed_actions_ordering():
    # SET, REMOVE, ADD, DELETE should appear in that order in the expression string
    # regardless of method call order, because we group them in _compile.
    builder = (
        User.update("pk")
        .add(User.age, 1)
        .set(User.name, "Bob")
        .delete(User.tags, {"old"})
        .remove(User.score)
    )

    params = builder._compile()
    expr = params["UpdateExpression"]

    # Expected: SET ... REMOVE ... ADD ... DELETE ...
    # Check strict ordering of sections
    parts = expr.split(" ")
    keywords = [p for p in parts if p in ["SET", "REMOVE", "ADD", "DELETE"]]
    assert keywords == ["SET", "REMOVE", "ADD", "DELETE"]


def test_set_none_becomes_remove():
    # User.update(...).set(User.name, None) -> Should become REMOVE name
    builder = User.update("pk").set(User.name, None)
    params = builder._compile()

    assert params["UpdateExpression"] == "REMOVE #u_n0"
    assert params["ExpressionAttributeNames"] == {"#u_n0": "name"}


def test_pydantic_validation_success():
    # Age is int. Passing "30" (string) should be coerced to int 30 if pydantic allows,
    # or validated. Pydantic standard mode allows str->int coercion.
    builder = User.update("pk").set(User.age, "30")
    params = builder._compile()
    assert params["ExpressionAttributeValues"][":u_v0"]["N"] == "30"


def test_pydantic_validation_failure():
    # Age is int. Passing "invalid" should raise.
    builder = User.update("pk").set(User.age, "invalid")

    with pytest.raises(ValueError, match="Validation failed for field 'age'"):
        builder._compile()


def test_condition_integration():
    builder = User.update("pk").set(User.name, "Bob").condition(User.age > 18)

    params = builder._compile()

    assert params["UpdateExpression"] == "SET #u_n0 = :u_v0"
    assert "ConditionExpression" in params
    # Condition uses boto3 placeholders (#n0, :v0) usually, Updates use #u_...
    # We just ensure they successfully merged.

    assert "#u_n0" in params["ExpressionAttributeNames"]  # Update name
    # Condition names should also be there
    # For User.age > 18: name placeholder for age, value placeholder for 18
    assert len(params["ExpressionAttributeNames"]) >= 2
    assert len(params["ExpressionAttributeValues"]) >= 2


def test_reserved_keywords_aliasing():
    # 'name' is a reserved keyword in DynamoDB.
    # Our system always aliases, but verify it works.
    builder = User.update("pk").set(User.name, "Name")
    params = builder._compile()
    assert "#u_n0" in params["UpdateExpression"]
    assert params["ExpressionAttributeNames"]["#u_n0"] == "name"
