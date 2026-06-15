from unittest.mock import MagicMock

import pytest

from dynantic.query import DynamoQueryBuilder
from dynantic.scan import DynamoScanBuilder


def _setup_count_pages(client, counts):
    paginator = MagicMock()
    paginator.paginate.return_value = [{"Count": c} for c in counts]
    client.get_paginator.return_value = paginator
    return paginator


@pytest.mark.unit
class TestCount:
    def test_count_sums_pages_and_uses_select_count(self, inject_mock_client, sample_user_model):
        paginator = _setup_count_pages(inject_mock_client, [3, 2])

        total = DynamoQueryBuilder(sample_user_model, "x").count()

        assert total == 5
        assert paginator.paginate.call_args.kwargs["Select"] == "COUNT"

    def test_count_respects_limit(self, inject_mock_client, sample_user_model):
        _setup_count_pages(inject_mock_client, [3, 3])

        total = DynamoQueryBuilder(sample_user_model, "x").limit(4).count()

        assert total == 4

    def test_count_scan(self, inject_mock_client, sample_user_model):
        paginator = _setup_count_pages(inject_mock_client, [7])

        total = DynamoScanBuilder(sample_user_model).count()

        assert total == 7
        assert paginator.paginate.call_args.kwargs["Select"] == "COUNT"
