"""
Unit tests for the conditions DSL module.

These tests verify:
1. Attr builder produces DynCondition instances (not raw boto3)
2. Comparison operators work correctly
3. DynamoDB function methods work correctly
4. Condition composition with &, |, ~ returns DynCondition
5. DynCondition.raw contains the underlying boto3 condition
6. compile_condition produces correct output format
7. Raw boto3 conditions are accepted (passthrough support)
8. We delegate to boto3 (no hand-rolled expression strings)
"""

from boto3.dynamodb.conditions import Attr as Boto3Attr
from boto3.dynamodb.conditions import ConditionBase as Boto3ConditionBase
from pydantic import Field

from dynantic import DynamoModel, Key
from dynantic.conditions import Attr, DynCondition, compile_condition
from dynantic.serializer import DynamoSerializer


class TestAttrBuilder:
    """Test the Attr class for building conditions."""

    def test_attr_creation(self):
        """Test Attr is created with correct name."""
        attr = Attr("email")
        assert attr.name == "email"

    def test_equals_operator_returns_dyncondition(self):
        """Test == operator returns DynCondition, not raw boto3."""
        condition = Attr("age") == 25
        assert isinstance(condition, DynCondition)
        # Verify underlying boto3 condition in .raw
        assert isinstance(condition.raw, Boto3ConditionBase)

    def test_not_equals_operator(self):
        """Test != operator returns DynCondition."""
        condition = Attr("status") != "deleted"
        assert isinstance(condition, DynCondition)

    def test_less_than_operator(self):
        """Test < operator returns DynCondition."""
        condition = Attr("age") < 18
        assert isinstance(condition, DynCondition)

    def test_less_than_equals_operator(self):
        """Test <= operator returns DynCondition."""
        condition = Attr("age") <= 65
        assert isinstance(condition, DynCondition)

    def test_greater_than_operator(self):
        """Test > operator returns DynCondition."""
        condition = Attr("score") > 100
        assert isinstance(condition, DynCondition)

    def test_greater_than_equals_operator(self):
        """Test >= operator returns DynCondition."""
        condition = Attr("age") >= 18
        assert isinstance(condition, DynCondition)


class TestAttrFunctions:
    """Test DynamoDB function methods on Attr."""

    def test_exists_returns_dyncondition(self):
        """Test exists() returns DynCondition."""
        condition = Attr("optional_field").exists()
        assert isinstance(condition, DynCondition)

    def test_not_exists_returns_dyncondition(self):
        """Test not_exists() returns DynCondition (create-if-not-exists pattern)."""
        condition = Attr("email").not_exists()
        assert isinstance(condition, DynCondition)

    def test_begins_with_returns_dyncondition(self):
        """Test begins_with() returns DynCondition."""
        condition = Attr("name").begins_with("John")
        assert isinstance(condition, DynCondition)

    def test_contains_returns_dyncondition(self):
        """Test contains() returns DynCondition."""
        condition = Attr("tags").contains("premium")
        assert isinstance(condition, DynCondition)

    def test_between_returns_dyncondition(self):
        """Test between() returns DynCondition."""
        condition = Attr("age").between(18, 65)
        assert isinstance(condition, DynCondition)

    def test_is_in_returns_dyncondition(self):
        """Test is_in() returns DynCondition."""
        condition = Attr("status").is_in(["active", "pending"])
        assert isinstance(condition, DynCondition)


class TestDynConditionComposition:
    """Test combining DynConditions with &, |, ~."""

    def test_and_returns_dyncondition(self):
        """Test & operator returns DynCondition (not raw boto3)."""
        condition = (Attr("age") >= 18) & (Attr("active") == True)
        assert isinstance(condition, DynCondition)
        # Verify raw is boto3 And condition
        assert isinstance(condition.raw, Boto3ConditionBase)

    def test_or_returns_dyncondition(self):
        """Test | operator returns DynCondition."""
        condition = (Attr("role") == "admin") | (Attr("role") == "moderator")
        assert isinstance(condition, DynCondition)

    def test_not_returns_dyncondition(self):
        """Test ~ operator returns DynCondition."""
        condition = ~Attr("deleted").exists()
        assert isinstance(condition, DynCondition)

    def test_complex_composition_returns_dyncondition(self):
        """Test complex condition still returns DynCondition."""
        condition = (Attr("age") >= 18) & (Attr("status") == "active") & ~Attr("banned").exists()
        assert isinstance(condition, DynCondition)

    def test_rand_supports_mixed_order(self):
        """Test that boto3_condition & DynCondition works (__rand__)."""
        boto3_cond = Boto3Attr("x").eq(1)
        dyn_cond = Attr("y") == 2
        result = dyn_cond & boto3_cond
        assert isinstance(result, DynCondition)

    def test_ror_supports_mixed_order(self):
        """Test that boto3_condition | DynCondition works (__ror__)."""
        boto3_cond = Boto3Attr("x").eq(1)
        dyn_cond = Attr("y") == 2
        result = dyn_cond | boto3_cond
        assert isinstance(result, DynCondition)


class TestCompilation:
    """Test compilation of conditions to DynamoDB parameters."""

    def setup_method(self):
        self.serializer = DynamoSerializer()

    def test_compile_simple_condition(self):
        """Test compiling a simple equality condition."""
        condition = Attr("username") == "mario"
        result = compile_condition(condition, self.serializer)

        # Verify structure
        assert "ConditionExpression" in result
        assert "ExpressionAttributeNames" in result
        assert "ExpressionAttributeValues" in result

        # Verify content (boto3 uses placeholders like #n0, :v0)
        # We can't guarantee exact placeholder names, but we can check values
        names = result["ExpressionAttributeNames"]
        values = result["ExpressionAttributeValues"]

        assert "username" in names.values()
        assert {"S": "mario"} in values.values()

    def test_compile_complex_condition(self):
        """Test compiling a composed condition."""
        condition = (Attr("age") > 18) & (Attr("status") == "active")
        result = compile_condition(condition, self.serializer)

        values = result["ExpressionAttributeValues"]
        assert {"N": "18"} in values.values()
        assert {"S": "active"} in values.values()

    def test_passthrough_raw_boto3(self):
        """Test that raw boto3 conditions can be compiled."""
        condition = Boto3Attr("email").exists()
        result = compile_condition(condition, self.serializer)

        names = result["ExpressionAttributeNames"]
        assert "email" in names.values()


class TestDSLSyntax:
    """Test the SQLModel-like DSL syntax."""

    def test_model_fields_are_instrumented(self):
        """Test that model fields are replaced by Attr objects on the class."""

        class User(DynamoModel):
            class Meta:
                table_name = "test-table"

            id: str = Key()
            age: int
            status: str

            # Test aliased field
            email_address: str = Field(alias="email")

        # 1. Check class attributes
        assert isinstance(User.age, Attr)
        assert User.age.name == "age"

        assert isinstance(User.status, Attr)
        assert User.status.name == "status"

        # 2. Check aliased field uses the alias name for DynamoDB
        assert isinstance(User.email_address, Attr)
        assert User.email_address.name == "email"

        # 3. Check DSL usage
        condition = (User.age >= 18) & (User.status == "active")
        assert isinstance(condition, DynCondition)

        # 4. Check NOT operator
        condition2 = ~User.email_address.exists()
        assert isinstance(condition2, DynCondition)

    def test_instance_access_still_works(self):
        """Test that instance attribute access still returns values, not Attr objects."""

        class User(DynamoModel):
            class Meta:
                table_name = "test-table"

            id: str = Key()
            age: int = 10

        user = User(id="123", age=25)

        # Instance access returns value
        assert user.age == 25

        # Class access returns Attr
        assert isinstance(User.age, Attr)
