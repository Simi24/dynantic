from unittest.mock import MagicMock

import pytest

from dynantic.conditions import Attr
from dynantic.query import DynamoQueryBuilder
from dynantic.scan import DynamoScanBuilder


def _setup_paginate(client, items):
    paginator = MagicMock()
    paginator.paginate.return_value = [{"Items": items}]
    client.get_paginator.return_value = paginator
    return paginator


@pytest.mark.unit
class TestProjectionValues:
    def test_values_builds_projection_expression(self, inject_mock_client, sample_user_model):
        items = [{"email": {"S": "a@b.com"}, "username": {"S": "alice"}}]
        paginator = _setup_paginate(inject_mock_client, items)

        rows = DynamoQueryBuilder(sample_user_model, "a@b.com").values("email", "username")

        assert rows == [{"email": "a@b.com", "username": "alice"}]
        kwargs = paginator.paginate.call_args.kwargs
        assert kwargs["ProjectionExpression"] == "#p_n0, #p_n1"
        names = kwargs["ExpressionAttributeNames"]
        assert names["#p_n0"] == "email"
        assert names["#p_n1"] == "username"

    def test_values_accepts_attr_objects(self, inject_mock_client, sample_user_model):
        # Metaclass instruments class attributes as Attr() for the DSL
        assert isinstance(sample_user_model.email, Attr)
        items = [{"email": {"S": "a@b.com"}}]
        paginator = _setup_paginate(inject_mock_client, items)

        rows = DynamoQueryBuilder(sample_user_model, "a@b.com").values(sample_user_model.email)

        assert rows == [{"email": "a@b.com"}]
        assert paginator.paginate.call_args.kwargs["ProjectionExpression"] == "#p_n0"

    def test_values_dedups_repeated_fields(self, inject_mock_client, sample_user_model):
        paginator = _setup_paginate(inject_mock_client, [])

        DynamoQueryBuilder(sample_user_model, "a@b.com").values("email", "email")

        kwargs = paginator.paginate.call_args.kwargs
        assert kwargs["ProjectionExpression"] == "#p_n0, #p_n0"
        assert kwargs["ExpressionAttributeNames"]["#p_n0"] == "email"

    def test_values_requires_at_least_one_field(self, inject_mock_client, sample_user_model):
        with pytest.raises(ValueError, match="requires at least one field"):
            DynamoQueryBuilder(sample_user_model, "a@b.com").values()

    def test_values_returns_plain_dicts_not_models(self, inject_mock_client, sample_user_model):
        # Item is missing required fields (age/username) -> would fail Pydantic.
        # values() must bypass validation and return raw dicts.
        items = [{"email": {"S": "a@b.com"}}]
        _setup_paginate(inject_mock_client, items)

        rows = DynamoQueryBuilder(sample_user_model, "a@b.com").values("email")

        assert rows == [{"email": "a@b.com"}]
        assert all(isinstance(r, dict) for r in rows)

    def test_scan_values(self, inject_mock_client, sample_user_model):
        items = [{"email": {"S": "a@b.com"}}]
        paginator = _setup_paginate(inject_mock_client, items)

        rows = DynamoScanBuilder(sample_user_model).values("email")

        assert rows == [{"email": "a@b.com"}]
        assert "ProjectionExpression" in paginator.paginate.call_args.kwargs


@pytest.mark.unit
class TestProjectionValuesList:
    def test_values_list_returns_flat_values(self, inject_mock_client, sample_user_model):
        items = [{"email": {"S": "a@b.com"}}, {"email": {"S": "c@d.com"}}]
        _setup_paginate(inject_mock_client, items)

        emails = DynamoQueryBuilder(sample_user_model, "x").values_list("email")

        assert emails == ["a@b.com", "c@d.com"]

    def test_values_list_missing_attribute_yields_none(self, inject_mock_client, sample_user_model):
        items = [{"username": {"S": "alice"}}]
        _setup_paginate(inject_mock_client, items)

        result = DynamoQueryBuilder(sample_user_model, "x").values_list("email")

        assert result == [None]
