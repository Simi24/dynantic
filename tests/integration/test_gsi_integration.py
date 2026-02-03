"""
Integration tests for Global Secondary Index (GSI) functionality.

These tests verify that GSI queries and scans work correctly against LocalStack.
"""

import pytest


@pytest.mark.integration
class TestGSIQueryIntegration:
    """Test GSI query operations against LocalStack."""

    def test_query_gsi_partition_key_only(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test querying GSI with partition key only."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Query by customer_id (GSI partition key only)
        orders = integration_order_model.query_index("customer-index", "CUST-123").all()

        # Should return 2 orders for CUST-123
        assert len(orders) == 2
        assert all(order.customer_id == "CUST-123" for order in orders)
        order_ids = {order.order_id for order in orders}
        assert order_ids == {"ORD-001", "ORD-002"}

    def test_query_gsi_with_sort_key_condition(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test querying GSI with partition key and sort key conditions."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Query by status with date range (GSI with partition and sort keys)
        orders = (
            integration_order_model.query_index("status-date-index", "PENDING")
            .between("2023-01-15", "2023-01-20")
            .all()
        )

        # Should return PENDING orders within date range
        assert len(orders) == 3
        assert all(order.status == "PENDING" for order in orders)
        order_ids = {order.order_id for order in orders}
        assert order_ids == {"ORD-001", "ORD-003", "ORD-005"}

    def test_query_gsi_with_starts_with(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test querying GSI with starts_with condition."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Query by status with starts_with on date
        orders = (
            integration_order_model.query_index("status-date-index", "PENDING")
            .starts_with("2023-01-1")
            .all()
        )

        # Should return PENDING orders starting with "2023-01-1"
        assert len(orders) == 3
        assert all(order.status == "PENDING" for order in orders)
        assert all(order.order_date.startswith("2023-01-1") for order in orders)

    def test_query_gsi_with_limit(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test querying GSI with limit."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Query with limit
        orders = integration_order_model.query_index("customer-index", "CUST-123").limit(1).all()

        # Should return only 1 order
        assert len(orders) == 1
        assert orders[0].customer_id == "CUST-123"

    def test_query_gsi_reverse_order(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test querying GSI with reverse order."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Query in reverse order (descending)
        orders = integration_order_model.query_index("status-date-index", "PENDING").reverse().all()

        # Should return PENDING orders in reverse date order
        assert len(orders) == 3
        assert all(order.status == "PENDING" for order in orders)
        # Check that dates are in descending order
        dates = [order.order_date for order in orders]
        assert dates == sorted(dates, reverse=True)

    def test_query_gsi_no_results(self, clean_gsi_tables, integration_order_model):
        """Test querying GSI with no matching results."""
        # Query for non-existent customer
        orders = integration_order_model.query_index("customer-index", "NONEXISTENT").all()

        assert len(orders) == 0

    def test_query_gsi_invalid_index(self, clean_gsi_tables, integration_order_model):
        """Test querying with invalid GSI name raises error."""
        with pytest.raises(ValueError, match="is not defined on model"):
            integration_order_model.query_index("invalid-index", "value")


@pytest.mark.integration
class TestGSIScanIntegration:
    """Test GSI scan operations against LocalStack."""

    def test_scan_gsi_table(self, clean_gsi_tables, integration_order_model, sample_orders_data):
        """Test scanning a GSI."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Scan the customer-index GSI
        orders = list(integration_order_model.scan(index_name="customer-index"))

        # Should return all orders (GSI scan returns all items)
        assert len(orders) == 5
        customer_ids = {order.customer_id for order in orders}
        assert customer_ids == {"CUST-123", "CUST-456", "CUST-789"}

    def test_scan_gsi_with_limit(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test scanning GSI with limit."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Scan with limit
        orders = list(integration_order_model.scan(index_name="customer-index").limit(2))

        assert len(orders) == 2

    def test_scan_invalid_gsi_raises_error(self, clean_gsi_tables, integration_order_model):
        """Test scanning with invalid GSI name raises error."""
        with pytest.raises(ValueError, match="is not defined on model"):
            list(integration_order_model.scan(index_name="invalid-index"))

    def test_scan_main_table_vs_gsi(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test that scanning main table vs GSI returns same data."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Scan main table
        main_table_orders = list(integration_order_model.scan())
        assert len(main_table_orders) == 5

        # Scan GSI (should return same items, just accessible via different key)
        gsi_orders = list(integration_order_model.scan(index_name="customer-index"))
        assert len(gsi_orders) == 5

        # Items should be the same (though possibly in different order)
        main_order_ids = {order.order_id for order in main_table_orders}
        gsi_order_ids = {order.order_id for order in gsi_orders}
        assert main_order_ids == gsi_order_ids


@pytest.mark.integration
class TestGSIComplexScenarios:
    """Test complex GSI scenarios."""

    def test_multiple_gsi_queries(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test querying multiple GSIs in sequence."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Query customer-index
        customer_orders = integration_order_model.query_index("customer-index", "CUST-123").all()
        assert len(customer_orders) == 2

        # Query status-date-index
        pending_orders = integration_order_model.query_index("status-date-index", "PENDING").all()
        assert len(pending_orders) == 3

        # Query delivered orders
        delivered_orders = integration_order_model.query_index(
            "status-date-index", "DELIVERED"
        ).all()
        assert len(delivered_orders) == 1
        assert delivered_orders[0].order_id == "ORD-004"

    def test_gsi_query_builder_chaining(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test complex query builder chaining with GSI."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Complex query: status = PENDING, date between range, limit results
        orders = (
            integration_order_model.query_index("status-date-index", "PENDING")
            .between("2023-01-10", "2023-01-20")
            .limit(2)
            .all()
        )

        assert len(orders) == 2
        assert all(order.status == "PENDING" for order in orders)
        assert all("2023-01-1" in order.order_date for order in orders)

    def test_gsi_sort_key_only_condition(
        self, clean_gsi_tables, integration_order_model, sample_orders_data
    ):
        """Test GSI query with only sort key condition (should work for range queries)."""
        # Seed data
        for order_data in sample_orders_data:
            order = integration_order_model(**order_data)
            order.save()

        # Query with eq on sort key (this should work for exact matches)
        # Note: In DynamoDB, you can't query only by sort key without partition key,
        # but our implementation should handle this gracefully
        orders = (
            integration_order_model.query_index("status-date-index", "PENDING")
            .eq("2023-01-15")
            .all()
        )

        assert len(orders) == 1
        assert orders[0].order_id == "ORD-001"
        assert orders[0].order_date == "2023-01-15"
