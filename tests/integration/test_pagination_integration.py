"""
Integration tests for pagination functionality against LocalStack.

Tests the page() and scan_page() methods with real DynamoDB operations.
"""

import pytest


@pytest.mark.integration
class TestQueryPaginationIntegration:
    """Test query pagination with real DynamoDB operations."""

    def test_query_page_first_page(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test getting the first page of query results."""
        # Save multiple messages
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Get first page with limit
        page = integration_message_model.query("general").limit(2).page()

        # Should return at most 2 items
        assert len(page.items) <= 2
        assert page.count == len(page.items)

        # Should have cursor if there are more items
        total_general_messages = len([m for m in messages if m.room_id == "general"])
        if total_general_messages > 2:
            assert page.last_evaluated_key is not None
            assert page.has_more is True
        else:
            assert page.last_evaluated_key is None
            assert page.has_more is False

    def test_query_page_with_cursor(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test getting subsequent pages using cursor."""
        # Save multiple messages
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Get first page
        page1 = integration_message_model.query("general").limit(2).page()

        if page1.has_more:
            # Get second page using cursor
            page2 = (
                integration_message_model.query("general")
                .limit(2)
                .page(start_key=page1.last_evaluated_key)
            )

            # Should have different items
            page1_ids = {(item.room_id, item.timestamp) for item in page1.items}
            page2_ids = {(item.room_id, item.timestamp) for item in page2.items}
            assert page1_ids.isdisjoint(page2_ids)

            # Both pages should have items
            assert len(page1.items) > 0
            assert len(page2.items) > 0

    def test_query_page_all_pages_loop(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test looping through all pages until no more results."""
        # Save multiple messages
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Collect all items through pagination
        all_paginated_items = []
        cursor = None
        page_count = 0

        while True:
            page = integration_message_model.query("general").limit(2).page(start_key=cursor)
            all_paginated_items.extend(page.items)
            page_count += 1

            if not page.has_more:
                break

            cursor = page.last_evaluated_key

        # Should get all messages for the room
        expected_count = len([m for m in messages if m.room_id == "general"])
        assert len(all_paginated_items) == expected_count

        # Should have used multiple pages if there were enough items
        if expected_count > 2:
            assert page_count > 1

    def test_query_page_empty_result(self, clean_integration_tables, integration_message_model):
        """Test query page when no results match."""
        page = integration_message_model.query("nonexistent_room").page()

        assert page.items == []
        assert page.count == 0
        assert page.last_evaluated_key is None
        assert page.has_more is False

    def test_query_page_with_sort_key_condition(
        self, clean_integration_tables, integration_message_model, sample_messages_data
    ):
        """Test query page with sort key conditions."""
        # Save messages with different timestamps
        messages = []
        for msg_data in sample_messages_data:
            if msg_data["room_id"] == "general":
                message = integration_message_model(**msg_data)
                message.save()
                messages.append(message)

        # Get messages after a certain timestamp
        timestamps = sorted([m.timestamp for m in messages])
        if len(timestamps) > 1:
            threshold = timestamps[1]  # Second timestamp

            page = integration_message_model.query("general").ge(threshold).limit(2).page()

            # All returned items should be >= threshold
            for item in page.items:
                assert item.timestamp >= threshold


@pytest.mark.integration
class TestScanPaginationIntegration:
    """Test scan pagination with real DynamoDB operations."""

    def test_scan_page_first_page(self, clean_integration_tables, integration_user_model):
        """Test getting the first page of scan results."""
        users_data = [
            {
                "email": f"user{i}@example.com",
                "username": f"user{i}",
                "age": 20 + i,
                "score": 80.0 + i,
            }
            for i in range(10)
        ]

        for user_data in users_data:
            integration_user_model(**user_data).save()

        page = integration_user_model.scan().limit(3).page()

        assert len(page.items) <= 3
        assert page.count == len(page.items)
        assert page.has_more is True
        assert page.last_evaluated_key is not None

    def test_scan_page_with_cursor(self, clean_integration_tables, integration_user_model):
        """Test getting subsequent pages using cursor."""
        users_data = [
            {
                "email": f"user{i:02d}@example.com",
                "username": f"user{i:02d}",
                "age": 20 + i,
                "score": 80.0 + i,
            }
            for i in range(10)
        ]

        for user_data in users_data:
            integration_user_model(**user_data).save()

        page1 = integration_user_model.scan().limit(3).page()
        page2 = integration_user_model.scan().limit(3).page(
            start_key=page1.last_evaluated_key
        )

        page1_emails = {item.email for item in page1.items}
        page2_emails = {item.email for item in page2.items}
        assert page1_emails.isdisjoint(page2_emails)
        assert len(page1.items) > 0
        assert len(page2.items) > 0

    def test_scan_page_all_items_loop(self, clean_integration_tables, integration_user_model):
        """Test scanning all items through pagination."""
        users_data = [
            {
                "email": f"user{i:02d}@example.com",
                "username": f"user{i:02d}",
                "age": 20 + i,
                "score": 80.0 + i,
            }
            for i in range(15)
        ]

        for user_data in users_data:
            integration_user_model(**user_data).save()

        all_paginated_items = []
        cursor = None

        while True:
            page = integration_user_model.scan().limit(4).page(start_key=cursor)
            all_paginated_items.extend(page.items)

            if not page.has_more:
                break

            cursor = page.last_evaluated_key

        assert len(all_paginated_items) == 15

        result_emails = {item.email for item in all_paginated_items}
        expected_emails = {user["email"] for user in users_data}
        assert result_emails == expected_emails

    def test_scan_page_empty_table(self, clean_integration_tables, integration_user_model):
        """Test scan page on empty table."""
        page = integration_user_model.scan().limit(10).page()

        assert page.items == []
        assert page.count == 0
        assert page.last_evaluated_key is None
        assert page.has_more is False
