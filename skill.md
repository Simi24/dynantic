# Dynantic Usage Skill

This skill teaches a coding agent how to use the `dynantic` library for interacting with Amazon DynamoDB.

## 1. Introduction

Dynantic is a synchronous-first Python ORM for Amazon DynamoDB that uses Pydantic v2 for type validation. It provides a metaclass-based DSL for building queries and simplifies interaction with DynamoDB.

**Core Features:**
- Pydantic v2 validation.
- Elegant DSL for queries, updates, and conditions.
- Support for GSIs, polymorphic models, and atomic updates.
- Optimized for serverless environments like AWS Lambda.

## 2. Core Principles

- **Sync-first**: Dynantic is synchronous. For async frameworks like FastAPI, use `asyncio.to_thread`.
- **Pydantic-based**: Models are Pydantic models. Leverage Pydantic features for validation.
- **Explicit is better than implicit**: Operations are explicit (e.g., `save()`, `delete()`, `query()`).
- **Manage your own infrastructure**: Dynantic does not create or migrate tables. Use Infrastructure as Code (IaC) like Terraform or AWS CDK.
- **Mypy Compliance**: For type-safe code that passes `mypy`, use `Attr("field_name")` for filtering and conditions instead of the metaclass DSL (`Model.field_name`). The DSL works at runtime but will fail static analysis.

## 3. Model Definition

Define a model by inheriting from `dynantic.DynamoModel`. Use Pydantic type hints for attributes.

### Keys and Indexes

- `Key()`: Defines the partition key.
- `SortKey()`: Defines the sort key.
- `GSIKey(index_name="...")`: Defines a GSI partition key.
- `GSISortKey(index_name="...")`: Defines a GSI sort key.

**Example: Basic Model**
```python
from dynantic import DynamoModel, Key

class Product(DynamoModel):
    product_id: str = Key()
    name: str
    price: float

    class Meta:
        table_name = "products"
```

**Example: Model with GSI**
```python
from datetime import datetime
from dynantic import DynamoModel, Key, GSIKey, GSISortKey

class BlogPost(DynamoModel):
    post_id: str = Key()
    title: str
    
    # GSI for querying by category
    category: str = GSIKey(index_name="CategoryIndex")
    published_at: datetime = GSISortKey(index_name="CategoryIndex")

    class Meta:
        table_name = "blog_posts"
```

## 4. CRUD Operations

### Create (`save`)
Instantiate a model and call `.save()`.
```python
product = Product(product_id="prod-123", name="Widget", price=29.99)
product.save()
```

### Read (`get`)
Use the class method `.get()` with the partition key (and sort key if applicable). It returns `None` if the item is not found.
```python
# By partition key
product = Product.get("prod-123")

# By partition and sort key
# order = Order.get("customer-456", "order-789")
```

### Update (`save` or atomic `update`)
- **Fetch-and-save**: `get()` the item, modify its attributes, and `save()` it.
- **Atomic update**: Use `.update()` for atomic operations without a prior read (see section 6).

```python
product = Product.get("prod-123")
if product:
    product.price = 34.99
    product.save()
```

### Delete (`delete` or `delete_item`)
- **By key**: Use the class method `.delete()`.
- **From instance**: Call `.delete_item()` on a model instance.

```python
# By key
Product.delete("prod-123")

# From instance
product = Product.get("prod-123")
if product:
    product.delete_item()
```

## 5. Querying and Scanning

### Query (`query`)
Use `.query(partition_key)` to query a table. It returns a `QueryBuilder` object. Chain methods to refine the query, and end with `.all()` or `.first()`.

**Sort Key Conditions:**
- `.eq(value)`: Equal to.
- `.starts_with(prefix)`: Begins with.
- `.between(low, high)`: Inclusive range.
- `.gt(value)`, `.gte(value)`, `.lt(value)`, `.lte(value)`: Comparisons.

```python
# Get all items with a given partition key
# orders = Order.query("customer-456").all()

# Query with sort key condition
# posts_2023 = BlogPost.query("author-123").starts_with("2023-").all()
```

### Query a GSI (`query_index`)
Use `.query_index(index_name, partition_key)`.
```python
# tech_posts = BlogPost.query_index("CategoryIndex", "technology").all()
```

### Scan (`scan`)
Use `.scan()` to scan the entire table. **Warning: Scans are expensive.** Use them sparingly.
```python
# This is just an example, avoid scanning large tables in production
# for user in User.scan(limit=100):
#     process_user(user)
```

### Filtering (`filter`)
Use `.filter()` on queries or scans to filter on non-key attributes. For mypy compliance, always use `Attr`.

**Filter Operators:** `==`, `!=`, `<`, `<=`, `>`, `>=`, `.contains()`, `.begins_with()`, `.exists()`, `.not_exists()`, `.between()`, `.is_in()`.
**Logical Operators:** `&` (AND), `|` (OR), `~` (NOT).

```python
from dynantic import Attr

# Mypy-compliant filter
# high_rated_movies = Movie.query(2013).filter(Attr("rating") >= 8.0).all()

# Complex filter
# condition = (Attr("age") >= 18) & (Attr("balance") > 0)
# eligible_users = User.scan().filter(condition).all()
```

## 6. Atomic Updates

Use the class method `.update()` to modify an item without reading it first. This is atomic and saves read capacity units (RCUs).

**Actions:**
- `set(field, value)`
- `add(field, value)` (for numbers or sets)
- `remove(field)`
- `delete(field, value)` (from a set)

Chain actions and finish with `.execute()`.
```python
# User.update("user-123", "john@example.com") \
#     .add(User.login_count, 1) \
#     .set(User.status, "active") \
#     .execute()
```

## 7. Conditional Writes

Add a `condition` to `save()`, `delete()`, or `update()` calls to perform the operation only if the condition is met. Always use `Attr` for mypy compliance.

```python
from dynantic import Attr

# Create if not exists
# user = User(...)
# user.save(condition=Attr("email").not_exists())

# Conditional delete
# User.delete("user-123", condition=Attr("balance") == 0)

# Optimistic locking
# user.save(condition=Attr("version") == 5)
```

## 8. Pagination

For stateless APIs, use `.page()` for queries and `.scan_page()` for scans. These methods return a `PageResult` object containing `items`, `has_more`, and `last_evaluated_key`.

Pass `last_evaluated_key` from one page as the `start_key` to the next request.

**Example: Query Pagination**
```python
# Get first page
# page1 = Order.query("customer-456").limit(10).page()

# Get next page
# if page1.has_more:
#     page2 = Order.query("customer-456").limit(10).page(start_key=page1.last_evaluated_key)
```

## 9. Polymorphism (Single-Table Design)

Define a base model with a `Discriminator()` field. Register subclasses with the `@BaseModel.register("discriminator_value")` decorator.

When you query or scan the base model, `dynantic` will automatically deserialize items into the correct subclass instances.

```python
from dynantic import DynamoModel, Key, Discriminator

class Animal(DynamoModel):
    animal_id: str = Key()
    type: str = Discriminator()

    class Meta:
        table_name = "animals"

@Animal.register("DOG")
class Dog(Animal):
    breed: str

@Animal.register("CAT")
class Cat(Animal):
    lives_remaining: int

# Dynantic automatically handles deserialization
# animals = Animal.scan()
# for animal in animals:
#     if isinstance(animal, Dog):
#         ...
```

## 10. Configuration

### AWS Credentials
Configure credentials via standard `boto3` methods (environment variables, IAM roles, etc.).

### Boto3 Client
You can provide a custom `boto3` client. This is useful for configuring retries, timeouts, or for testing.

```python
from botocore.config import Config
import boto3
from dynantic import DynamoModel

# Recommended: Create client once and set it globally
config = Config(retries={'max_attempts': 10, 'mode': 'adaptive'})
dynamo_client = boto3.client('dynamodb', config=config)
DynamoModel.set_client(dynamo_client)
```

For testing, you can use a mock client or a client pointed at LocalStack.

## 11. Async Usage

Dynantic is synchronous. To use it in an async application (e.g., FastAPI), run the synchronous `dynantic` calls in a thread pool.

```python
import asyncio
from fastapi import FastAPI

app = FastAPI()

# @app.get("/users/{user_id}")
# async def get_user(user_id: str):
#     # Safely run sync code in an async context
#     user = await asyncio.to_thread(User.get, user_id)
#     return user
```

## 12. Limitations

Be aware of features Dynantic does **not** support:
- **Native async**: Use `asyncio.to_thread`.
- **Transactions**: `transact_write_items` is not implemented. Use conditional writes.
- **Batch operations**: `batch_get_item`/`batch_write_item` are not implemented. Loop and perform individual operations.
- **Schema migrations**: You must create and manage tables yourself.

## 13. Best Practices & Security

- **Prefer Query over Scan**: Scans are slow and expensive. Design data models to use queries with key conditions.
- **Use `Attr()` for Mypy**: To avoid static analysis errors, use `Attr("field_name")` in filters and conditions.
- **Pagination Cursors**: Cursors are not encrypted. Do not trust them blindly. Always re-apply authorization and validation on the server side.
- **IAM**: Follow the principle of least privilege. Grant only the necessary DynamoDB permissions (`GetItem`, `PutItem`, etc.) to the specific tables and indexes your application needs.
- **Logging**: Be cautious with `DEBUG` level logging in production, as it may expose sensitive data. The default level is `INFO`.

```