from unittest.mock import patch

import pytest

from dynantic import DynamoModel, GSIKey, GSISortKey, Key, SortKey
from dynantic.query import DynamoQueryBuilder


class TestDynamoQueryBuilderInitialization:
    """Test DynamoQueryBuilder initialization and setup."""

    def test_init_sets_up_correctly(self, inject_mock_client, sample_user_model):
        """Test that initialization sets up all required attributes."""
        builder = DynamoQueryBuilder(sample_user_model, "user123")

        assert builder.model_cls == sample_user_model
        assert builder.pk_val == "user123"
        assert builder.sk_condition is None
        assert builder.limit_val is None
        assert builder.scan_forward is True
        assert builder.index_name is None
        assert ":pk" in builder.expression_values
        assert "#pk" in builder.expression_names
        assert builder.expression_names["#pk"] == "email"

    def test_init_with_message_model(self, inject_mock_client, sample_message_model):
        """Test initialization with a model that has sort key."""
        builder = DynamoQueryBuilder(sample_message_model, "room123")

        assert builder.model_cls == sample_message_model
        assert builder.pk_val == "room123"
        assert builder.expression_names["#pk"] == "room_id"


class TestDynamoQueryBuilderKeyConditions:
    """Test key condition methods (Sort Key conditions)."""

    def test_starts_with_sets_condition(self, inject_mock_client, sample_message_model):
        """Test starts_with method sets begins_with condition."""
        builder = DynamoQueryBuilder(sample_message_model, "room123")

        result = builder.starts_with("prefix_")

        assert result is builder  # Returns self for chaining
        assert builder.sk_condition == "begins_with(#sk, :sk)"
        assert "#sk" in builder.expression_names
        assert builder.expression_names["#sk"] == "timestamp"
        assert ":sk" in builder.expression_values

    def test_starts_with_raises_error_without_sort_key(self, inject_mock_client, sample_user_model):
        """Test starts_with raises error when no sort key defined."""
        builder = DynamoQueryBuilder(sample_user_model, "user123")

        with pytest.raises(ValueError, match="Index does not have a Sort Key defined"):
            builder.starts_with("prefix")

    def test_between_sets_condition(self, inject_mock_client, sample_message_model):
        """Test between method sets BETWEEN condition."""
        builder = DynamoQueryBuilder(sample_message_model, "room123")

        result = builder.between("low", "high")

        assert result is builder
        assert builder.sk_condition == "#sk BETWEEN :low AND :high"
        assert ":low" in builder.expression_values
        assert ":high" in builder.expression_values

    def test_gt_sets_condition(self, inject_mock_client, sample_message_model):
        """Test gt method sets greater than condition."""
        builder = DynamoQueryBuilder(sample_message_model, "room123")

        result = builder.gt("value")

        assert result is builder
        assert builder.sk_condition == "#sk > :sk"

    def test_lt_sets_condition(self, inject_mock_client, sample_message_model):
        """Test lt method sets less than condition."""
        builder = DynamoQueryBuilder(sample_message_model, "room123")

        result = builder.lt("value")

        assert result is builder
        assert builder.sk_condition == "#sk < :sk"

    def test_ge_sets_condition(self, inject_mock_client, sample_message_model):
        """Test ge method sets greater than or equal condition."""
        builder = DynamoQueryBuilder(sample_message_model, "room123")

        result = builder.ge("value")

        assert result is builder
        assert builder.sk_condition == "#sk >= :sk"

    def test_le_sets_condition(self, inject_mock_client, sample_message_model):
        """Test le method sets less than or equal condition."""
        builder = DynamoQueryBuilder(sample_message_model, "room123")

        result = builder.le("value")

        assert result is builder
        assert builder.sk_condition == "#sk <= :sk"

    def test_eq_sets_condition(self, inject_mock_client, sample_message_model):
        """Test eq method sets equal condition."""
        builder = DynamoQueryBuilder(sample_message_model, "room123")

        result = builder.eq("value")

        assert result is builder
        assert builder.sk_condition == "#sk = :sk"

    def test_ne_sets_condition(self, inject_mock_client, sample_message_model):
        """Test ne method sets not equal condition."""
        builder = DynamoQueryBuilder(sample_message_model, "room123")

        result = builder.ne("value")

        assert result is builder
        assert builder.sk_condition == "#sk <> :sk"

    def test_all_condition_methods_raise_error_without_sort_key(
        self, inject_mock_client, sample_user_model
    ):
        """Test all condition methods raise error when no sort key defined."""
        builder = DynamoQueryBuilder(sample_user_model, "user123")

        condition_methods = [
            lambda: builder.starts_with("prefix"),
            lambda: builder.between("low", "high"),
            lambda: builder.gt("value"),
            lambda: builder.lt("value"),
            lambda: builder.ge("value"),
            lambda: builder.le("value"),
            lambda: builder.eq("value"),
            lambda: builder.ne("value"),
        ]

        for method in condition_methods:
            with pytest.raises(ValueError, match="Index does not have a Sort Key defined"):
                method()


class TestDynamoQueryBuilderOptions:
    """Test query option methods."""

    def test_limit_sets_limit_value(self, inject_mock_client, sample_user_model):
        """Test limit method sets limit value."""
        builder = DynamoQueryBuilder(sample_user_model, "user123")

        result = builder.limit(10)

        assert result is builder
        assert builder.limit_val == 10

    def test_reverse_sets_scan_forward_false(self, inject_mock_client, sample_user_model):
        """Test reverse method sets scan_forward to False."""
        builder = DynamoQueryBuilder(sample_user_model, "user123")

        result = builder.reverse()

        assert result is builder
        assert builder.scan_forward is False

    def test_using_index_sets_index_name(self, inject_mock_client):
        """Test using_index method sets index name."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            customer_id: str = GSIKey(index_name="customer-index")

        Order.set_client(inject_mock_client)
        builder = DynamoQueryBuilder(Order, "user123")

        result = builder.using_index("customer-index")

        assert result is builder
        assert builder.index_name == "customer-index"


class TestDynamoQueryBuilderExecution:
    """Test query execution methods."""

    def test_all_method_exists_and_returns_list_type(self, inject_mock_client, sample_user_model):
        """Test all method exists and returns correct type when mocked."""
        builder = DynamoQueryBuilder(sample_user_model, "user123")

        # Mock the entire __iter__ method to avoid actual DynamoDB calls
        with patch.object(builder, "__iter__", return_value=iter([])):
            results = builder.all()

        assert isinstance(results, list)

    def test_first_method_exists(self, inject_mock_client, sample_user_model):
        """Test first method exists and can be called."""
        builder = DynamoQueryBuilder(sample_user_model, "user123")

        # Mock the entire __iter__ method to avoid actual DynamoDB calls
        with patch.object(builder, "__iter__", return_value=iter([])):
            result = builder.first()

        # Should return None for empty iterator
        assert result is None

    def test_one_method_raises_error_when_no_items(self, inject_mock_client, sample_user_model):
        """Test one method raises error when no items found."""
        builder = DynamoQueryBuilder(sample_user_model, "user123")

        with patch.object(builder, "__iter__", return_value=iter([])):
            with pytest.raises(ValueError, match="No items found for this query"):
                builder.one()


class TestDynamoQueryBuilderMethodChaining:
    """Test method chaining functionality."""

    def test_method_chaining_works(self, inject_mock_client):
        """Test that methods can be chained together."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            customer_id: str = GSIKey(index_name="customer-index")

        Order.set_client(inject_mock_client)
        builder = DynamoQueryBuilder(Order, "user123")

        result = builder.limit(10).reverse().using_index("customer-index")

        assert result is builder
        assert builder.limit_val == 10
        assert builder.scan_forward is False
        assert builder.index_name == "customer-index"

    def test_complex_query_construction(self, inject_mock_client):
        """Test complex query with multiple conditions."""

        class Message(DynamoModel):
            class Meta:
                table_name = "messages"

            room_id: str = Key()
            timestamp: str = SortKey()
            date_index: str = GSIKey(index_name="DateIndex")

        Message.set_client(inject_mock_client)
        builder = DynamoQueryBuilder(Message, "room123")

        result = builder.between("2023-01", "2023-12").limit(50).using_index("DateIndex")

        assert result is builder
        assert builder.sk_condition == "#sk BETWEEN :low AND :high"
        assert builder.limit_val == 50
        assert builder.index_name == "DateIndex"


@pytest.mark.unit
class TestGSIQueryBuilder:
    """Test DynamoQueryBuilder with GSI functionality."""

    def test_init_with_gsi_sets_correct_keys(self, inject_mock_client):
        """Test that initializing with GSI sets the correct key names."""

        # Create a model with GSI
        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            customer_id: str = GSIKey(index_name="customer-index")
            status: str = GSIKey(index_name="status-index")
            order_date: str = GSISortKey(index_name="status-index")

        Order.set_client(inject_mock_client)

        # Initialize query builder for GSI
        builder = DynamoQueryBuilder(Order, "CUST-123", index_name="customer-index")

        assert builder.index_name == "customer-index"
        assert builder.pk_name == "customer_id"
        assert builder.sk_name is None  # This GSI has no sort key
        assert builder.expression_names["#pk"] == "customer_id"

    def test_init_with_gsi_with_sort_key(self, inject_mock_client):
        """Test GSI initialization with both partition and sort keys."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            status: str = GSIKey(index_name="status-date-index")
            order_date: str = GSISortKey(index_name="status-date-index")

        Order.set_client(inject_mock_client)

        builder = DynamoQueryBuilder(Order, "PENDING", index_name="status-date-index")

        assert builder.index_name == "status-date-index"
        assert builder.pk_name == "status"
        assert builder.sk_name == "order_date"
        assert builder.expression_names["#pk"] == "status"

    def test_init_with_unknown_gsi_raises_error(self, inject_mock_client, sample_user_model):
        """Test that initializing with unknown GSI raises error."""
        sample_user_model.set_client(inject_mock_client)

        with pytest.raises(ValueError, match="is not defined on model"):
            DynamoQueryBuilder(sample_user_model, "val", index_name="unknown-index")

    def test_using_index_switches_to_different_gsi(self, inject_mock_client):
        """Test using_index method switches to different GSI."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            customer_id: str = GSIKey(index_name="customer-index")
            status: str = GSIKey(index_name="status-index")
            order_date: str = GSISortKey(index_name="status-index")

        Order.set_client(inject_mock_client)

        # Start with customer-index
        builder = DynamoQueryBuilder(Order, "CUST-123", index_name="customer-index")
        assert builder.pk_name == "customer_id"
        assert builder.sk_name is None

        # Switch to status-index
        builder.using_index("status-index")
        assert builder.index_name == "status-index"
        assert builder.pk_name == "status"
        assert builder.sk_name == "order_date"
        assert builder.expression_names["#pk"] == "status"

    def test_using_index_with_unknown_gsi_raises_error(self, inject_mock_client, sample_user_model):
        """Test using_index with unknown GSI raises error."""
        sample_user_model.set_client(inject_mock_client)
        builder = DynamoQueryBuilder(sample_user_model, "val")

        with pytest.raises(ValueError, match="is not defined on model"):
            builder.using_index("unknown-index")

    def test_gsi_condition_methods_use_gsi_keys(self, inject_mock_client):
        """Test that condition methods use GSI key names."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            status: str = GSIKey(index_name="status-date-index")
            order_date: str = GSISortKey(index_name="status-date-index")

        Order.set_client(inject_mock_client)

        builder = DynamoQueryBuilder(Order, "PENDING", index_name="status-date-index")

        # Test starts_with uses GSI sort key
        builder.starts_with("2023-01")
        assert builder.sk_condition == "begins_with(#sk, :sk)"
        assert builder.expression_names["#sk"] == "order_date"  # GSI SK name
        assert ":sk" in builder.expression_values

    def test_gsi_condition_methods_raise_error_without_gsi_sk(self, inject_mock_client):
        """Test condition methods raise error when GSI has no sort key."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            customer_id: str = GSIKey(index_name="customer-index")

        Order.set_client(inject_mock_client)

        builder = DynamoQueryBuilder(Order, "CUST-123", index_name="customer-index")

        with pytest.raises(ValueError, match="Index does not have a Sort Key defined"):
            builder.starts_with("prefix")

    def test_query_index_class_method(self, inject_mock_client):
        """Test the query_index class method."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            customer_id: str = GSIKey(index_name="customer-index")

        Order.set_client(inject_mock_client)

        builder = Order.query_index("customer-index", "CUST-123")

        assert isinstance(builder, DynamoQueryBuilder)
        assert builder.index_name == "customer-index"
        assert builder.pk_name == "customer_id"
        assert builder.pk_val == "CUST-123"

    def test_query_index_with_unknown_gsi_raises_error(self, inject_mock_client, sample_user_model):
        """Test query_index with unknown GSI raises error."""
        sample_user_model.set_client(inject_mock_client)

        with pytest.raises(ValueError, match="is not defined on model"):
            sample_user_model.query_index("unknown-index", "val")
