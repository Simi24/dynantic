"""
Unit tests for GSI metaclass discovery and ModelOptions.

Tests the metaclass logic for discovering GSI fields and building
GSI definitions at class creation time.
"""

import pytest

from dynantic import DynamoModel, GSIKey, GSISortKey, Key, SortKey


@pytest.mark.unit
class TestGSIMetaclassDiscovery:
    """Test GSI discovery by the DynamoMeta metaclass."""

    def test_discovers_single_gsi_partition_key_only(self):
        """Test discovering a GSI with only a partition key."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            customer_id: str = GSIKey(index_name="customer-index")
            total: float

        assert "customer-index" in Order._meta.gsi_definitions
        gsi = Order._meta.get_gsi("customer-index")
        assert gsi is not None
        assert gsi.pk_name == "customer_id"
        assert gsi.sk_name is None
        assert gsi.index_name == "customer-index"

    def test_discovers_gsi_with_sort_key(self):
        """Test discovering a GSI with both partition and sort keys."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            status: str = GSIKey(index_name="status-date-index")
            order_date: str = GSISortKey(index_name="status-date-index")
            total: float

        assert "status-date-index" in Order._meta.gsi_definitions
        gsi = Order._meta.get_gsi("status-date-index")
        assert gsi is not None
        assert gsi.pk_name == "status"
        assert gsi.sk_name == "order_date"
        assert gsi.index_name == "status-date-index"

    def test_discovers_multiple_gsis(self):
        """Test discovering multiple GSIs on the same model."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            customer_id: str = GSIKey(index_name="customer-index")
            status: str = GSIKey(index_name="status-date-index")
            order_date: str = GSISortKey(index_name="status-date-index")
            total: float

        # Check customer-index GSI
        assert "customer-index" in Order._meta.gsi_definitions
        customer_gsi = Order._meta.get_gsi("customer-index")
        assert customer_gsi is not None
        assert customer_gsi.pk_name == "customer_id"
        assert customer_gsi.sk_name is None

        # Check status-date-index GSI
        assert "status-date-index" in Order._meta.gsi_definitions
        status_gsi = Order._meta.get_gsi("status-date-index")
        assert status_gsi is not None
        assert status_gsi.pk_name == "status"
        assert status_gsi.sk_name == "order_date"

        # Check total count
        assert len(Order._meta.gsi_definitions) == 2

    def test_raises_error_for_gsi_without_partition_key(self):
        """Test that GSI without partition key raises error."""
        with pytest.raises(ValueError, match="must have a partition key"):

            class BadOrder(DynamoModel):
                class Meta:
                    table_name = "orders"

                order_id: str = Key()
                order_date: str = GSISortKey(index_name="orphan-index")
                total: float

    def test_raises_error_for_duplicate_gsi_partition_keys(self):
        """Test that duplicate GSI partition keys raise error."""
        with pytest.raises(ValueError, match="can have only one partition key"):

            class BadOrder(DynamoModel):
                class Meta:
                    table_name = "orders"

                order_id: str = Key()
                customer_id1: str = GSIKey(index_name="customer-index")
                customer_id2: str = GSIKey(index_name="customer-index")
                total: float

    def test_raises_error_for_duplicate_gsi_sort_keys(self):
        """Test that duplicate GSI sort keys raise error."""
        with pytest.raises(ValueError, match="can have only one sort key"):

            class BadOrder(DynamoModel):
                class Meta:
                    table_name = "orders"

                order_id: str = Key()
                status: str = GSIKey(index_name="status-index")
                date1: str = GSISortKey(index_name="status-index")
                date2: str = GSISortKey(index_name="status-index")
                total: float

    def test_gsi_does_not_interfere_with_main_table_keys(self):
        """Test that GSI fields don't interfere with main table key discovery."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            created_at: str = SortKey()
            customer_id: str = GSIKey(index_name="customer-index")
            status: str = GSIKey(index_name="status-index")
            order_date: str = GSISortKey(index_name="status-index")
            total: float

        # Main table keys should be correct
        assert Order._meta.pk_name == "order_id"
        assert Order._meta.sk_name == "created_at"

        # GSI keys should be separate
        customer_gsi = Order._meta.get_gsi("customer-index")
        status_gsi = Order._meta.get_gsi("status-index")
        assert customer_gsi is not None
        assert status_gsi is not None
        assert customer_gsi.pk_name == "customer_id"
        assert status_gsi.pk_name == "status"
        assert status_gsi.sk_name == "order_date"

    def test_has_gsi_method(self):
        """Test the has_gsi() method."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            customer_id: str = GSIKey(index_name="customer-index")
            total: float

        assert Order._meta.has_gsi("customer-index") is True
        assert Order._meta.has_gsi("nonexistent-index") is False

    def test_get_gsi_method_returns_none_for_unknown_index(self):
        """Test get_gsi() returns None for unknown index."""

        class Order(DynamoModel):
            class Meta:
                table_name = "orders"

            order_id: str = Key()
            total: float

        assert Order._meta.get_gsi("unknown-index") is None

    def test_model_without_gsis_has_empty_gsi_definitions(self):
        """Test that models without GSIs have empty gsi_definitions."""

        class User(DynamoModel):
            class Meta:
                table_name = "users"

            email: str = Key()
            name: str

        assert User._meta.gsi_definitions == {}
        assert len(User._meta.gsi_definitions) == 0
