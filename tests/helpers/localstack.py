"""
Integration test helpers for Dynantic.

This module provides utilities for setting up and managing LocalStack
resources during integration tests.
"""

import time
from typing import Any

import boto3
from botocore.exceptions import ClientError


class LocalStackHelper:
    """
    Helper class for managing LocalStack resources in integration tests.

    Provides methods for creating tables, seeding data, and cleaning up
    resources between tests.
    """

    def __init__(self, endpoint_url: str = "http://localhost:4566", region: str = "eu-south-1"):
        """Initialize LocalStack helper with connection details."""
        self.endpoint_url = endpoint_url
        self.region = region
        self.client = boto3.client(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

    def create_table(
        self,
        table_name: str,
        pk_name: str,
        pk_type: str = "S",
        sk_name: str | None = None,
        sk_type: str = "S",
        read_capacity: int = 5,
        write_capacity: int = 5,
    ) -> None:
        """
        Create a DynamoDB table with the specified schema.

        Args:
            table_name: Name of the table to create
            pk_name: Partition key attribute name
            pk_type: Partition key attribute type (S, N, B)
            sk_name: Sort key attribute name (optional)
            sk_type: Sort key attribute type (S, N, B)
            read_capacity: Read capacity units
            write_capacity: Write capacity units
        """
        key_schema = [{"AttributeName": pk_name, "KeyType": "HASH"}]
        attr_defs = [{"AttributeName": pk_name, "AttributeType": pk_type}]

        if sk_name:
            key_schema.append({"AttributeName": sk_name, "KeyType": "RANGE"})
            attr_defs.append({"AttributeName": sk_name, "AttributeType": sk_type})

        try:
            self.client.create_table(
                TableName=table_name,
                KeySchema=key_schema,
                AttributeDefinitions=attr_defs,
                ProvisionedThroughput={
                    "ReadCapacityUnits": read_capacity,
                    "WriteCapacityUnits": write_capacity,
                },
            )  # type: ignore[arg-type]

            # Wait for table to be active
            self.client.get_waiter("table_exists").wait(TableName=table_name)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                # Table already exists, just ensure it's active
                self.client.get_waiter("table_exists").wait(TableName=table_name)
            else:
                raise

    def create_table_with_gsi(
        self,
        table_name: str,
        pk_name: str,
        pk_type: str = "S",
        sk_name: str | None = None,
        sk_type: str = "S",
        gsi_definitions: list[dict[str, Any]] | None = None,
        read_capacity: int = 5,
        write_capacity: int = 5,
    ) -> None:
        """
        Create a DynamoDB table with Global Secondary Indexes.

        Args:
            table_name: Name of the table to create
            pk_name: Partition key attribute name
            pk_type: Partition key attribute type (S, N, B)
            sk_name: Sort key attribute name (optional)
            sk_type: Sort key attribute type (S, N, B)
            gsi_definitions: List of GSI definitions, each containing:
                - index_name: Name of the GSI
                - pk_name: GSI partition key attribute name
                - pk_type: GSI partition key type (S, N, B)
                - sk_name: GSI sort key attribute name (optional)
                - sk_type: GSI sort key type (S, N, B)
                - read_capacity: GSI read capacity units (default: 5)
                - write_capacity: GSI write capacity units (default: 5)
            read_capacity: Table read capacity units
            write_capacity: Table write capacity units
        """
        key_schema = [{"AttributeName": pk_name, "KeyType": "HASH"}]
        attr_defs = [{"AttributeName": pk_name, "AttributeType": pk_type}]

        if sk_name:
            key_schema.append({"AttributeName": sk_name, "KeyType": "RANGE"})
            attr_defs.append({"AttributeName": sk_name, "AttributeType": sk_type})

        global_secondary_indexes = []
        if gsi_definitions:
            for gsi_def in gsi_definitions:
                gsi_key_schema = [{"AttributeName": gsi_def["pk_name"], "KeyType": "HASH"}]
                gsi_attr_defs = [
                    {"AttributeName": gsi_def["pk_name"], "AttributeType": gsi_def["pk_type"]}
                ]

                if gsi_def.get("sk_name"):
                    gsi_key_schema.append({"AttributeName": gsi_def["sk_name"], "KeyType": "RANGE"})
                    gsi_attr_defs.append(
                        {"AttributeName": gsi_def["sk_name"], "AttributeType": gsi_def["sk_type"]}
                    )

                # Add GSI attribute definitions to main table attributes
                for attr_def in gsi_attr_defs:
                    if attr_def not in attr_defs:
                        attr_defs.append(attr_def)

                global_secondary_indexes.append(
                    {
                        "IndexName": gsi_def["index_name"],
                        "KeySchema": gsi_key_schema,
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": gsi_def.get("read_capacity", 5),
                            "WriteCapacityUnits": gsi_def.get("write_capacity", 5),
                        },
                    }
                )

        table_kwargs = {
            "TableName": table_name,
            "KeySchema": key_schema,
            "AttributeDefinitions": attr_defs,
            "ProvisionedThroughput": {
                "ReadCapacityUnits": read_capacity,
                "WriteCapacityUnits": write_capacity,
            },
        }

        if global_secondary_indexes:
            table_kwargs["GlobalSecondaryIndexes"] = global_secondary_indexes

        try:
            self.client.create_table(**table_kwargs)  # type: ignore[arg-type]

            # Wait for table to be active
            self.client.get_waiter("table_exists").wait(TableName=table_name)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                # Table already exists, just ensure it's active
                self.client.get_waiter("table_exists").wait(TableName=table_name)
            else:
                raise

    def delete_table(self, table_name: str) -> None:
        """
        Delete a DynamoDB table.

        Args:
            table_name: Name of the table to delete
        """
        try:
            self.client.delete_table(TableName=table_name)
            self.client.get_waiter("table_not_exists").wait(TableName=table_name)
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

    def put_item(self, table_name: str, item: dict[str, Any]) -> None:
        """
        Put an item into a DynamoDB table.

        Args:
            table_name: Name of the table
            item: Item data in DynamoDB JSON format
        """
        self.client.put_item(TableName=table_name, Item=item)

    def put_items(self, table_name: str, items: list[dict[str, Any]]) -> None:
        """
        Put multiple items into a DynamoDB table.

        Args:
            table_name: Name of the table
            items: List of items in DynamoDB JSON format
        """
        for item in items:
            self.put_item(table_name, item)

    def get_item(self, table_name: str, key: dict[str, Any]) -> dict[str, Any] | None:
        """
        Get an item from a DynamoDB table.

        Args:
            table_name: Name of the table
            key: Key attributes in DynamoDB JSON format

        Returns:
            Item data or None if not found
        """
        response = self.client.get_item(TableName=table_name, Key=key)
        return response.get("Item")

    def scan_table(self, table_name: str) -> list[dict[str, Any]]:
        """
        Scan all items from a DynamoDB table.

        Args:
            table_name: Name of the table

        Returns:
            List of all items in the table
        """
        items = []
        paginator = self.client.get_paginator("scan")

        for page in paginator.paginate(TableName=table_name):
            items.extend(page["Items"])

        return items

    def query_table(
        self,
        table_name: str,
        key_condition_expression: str,
        expression_attribute_values: dict[str, Any] | None = None,
        expression_attribute_names: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query a DynamoDB table.

        Args:
            table_name: Name of the table
            key_condition_expression: Key condition expression
            expression_attribute_values: Expression attribute values
            expression_attribute_names: Expression attribute names

        Returns:
            List of matching items
        """
        kwargs: dict[str, Any] = {
            "TableName": table_name,
            "KeyConditionExpression": key_condition_expression,
        }

        if expression_attribute_values:
            kwargs["ExpressionAttributeValues"] = expression_attribute_values

        if expression_attribute_names:
            kwargs["ExpressionAttributeNames"] = expression_attribute_names

        items = []
        paginator = self.client.get_paginator("query")

        for page in paginator.paginate(**kwargs):
            items.extend(page["Items"])

        return items

    def clear_table(self, table_name: str, pk_name: str, sk_name: str | None = None) -> None:
        """
        Delete all items from a table.

        Args:
            table_name: Name of the table
            pk_name: Partition key attribute name
            sk_name: Sort key attribute name (optional)
        """
        items = self.scan_table(table_name)

        for item in items:
            key = {pk_name: item[pk_name]}
            if sk_name and sk_name in item:
                key[sk_name] = item[sk_name]

            self.client.delete_item(TableName=table_name, Key=key)

    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Name of the table

        Returns:
            True if table exists, False otherwise
        """
        try:
            self.client.describe_table(TableName=table_name)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return False
            raise

    def wait_for_table_active(self, table_name: str, timeout: int = 30) -> None:
        """
        Wait for a table to become active.

        Args:
            table_name: Name of the table
            timeout: Maximum time to wait in seconds
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.client.describe_table(TableName=table_name)
                if response["Table"]["TableStatus"] == "ACTIVE":
                    return
            except ClientError:
                pass

            time.sleep(1)

        raise TimeoutError(f"Table {table_name} did not become active within {timeout} seconds")


def dynamo_json_to_python(dynamo_item: dict[str, Any]) -> dict[str, Any]:
    """
    Convert DynamoDB JSON format to Python types.

    Args:
        dynamo_item: Item in DynamoDB JSON format

    Returns:
        Item with Python types
    """
    result = {}

    for key, value in dynamo_item.items():
        if "S" in value:
            result[key] = value["S"]
        elif "N" in value:
            # Try to convert to int first, then float
            try:
                result[key] = int(value["N"])
            except ValueError:
                result[key] = float(value["N"])
        elif "BOOL" in value:
            result[key] = value["BOOL"]
        elif "L" in value:
            result[key] = [dynamo_json_to_python({"item": item})["item"] for item in value["L"]]
        elif "M" in value:
            result[key] = dynamo_json_to_python(value["M"])
        elif "SS" in value:
            result[key] = value["SS"]
        elif "NS" in value:
            # Convert number set to list of numbers
            result[key] = [float(n) for n in value["NS"]]
        elif "BS" in value:
            result[key] = value["BS"]
        else:
            result[key] = value

    return result


def python_to_dynamo_json(item: dict[str, Any]) -> dict[str, Any]:
    """
    Convert Python types to DynamoDB JSON format.

    Args:
        item: Item with Python types

    Returns:
        Item in DynamoDB JSON format
    """
    result: dict[str, Any] = {}

    for key, value in item.items():
        if isinstance(value, str):
            result[key] = {"S": value}
        elif isinstance(value, bool):
            result[key] = {"BOOL": value}
        elif isinstance(value, int):
            result[key] = {"N": str(value)}
        elif isinstance(value, float):
            result[key] = {"N": str(value)}
        elif isinstance(value, list):
            if value and isinstance(value[0], str):
                result[key] = {"SS": value}
            elif value and isinstance(value[0], (int, float)):
                result[key] = {"NS": [str(v) for v in value]}
            else:
                result[key] = {"L": [python_to_dynamo_json({"item": v})["item"] for v in value]}
        elif isinstance(value, dict):
            result[key] = {"M": python_to_dynamo_json(value)}
        else:
            # For bytes or other types, store as binary
            if isinstance(value, bytes):
                result[key] = {"B": value}
            else:
                result[key] = {"S": str(value)}

    return result
