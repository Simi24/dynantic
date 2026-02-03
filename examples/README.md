# Dynantic Examples

Examples demonstrating core features of the Dynantic library.

## Examples

### [model.py](./model.py)
AWS Movies table example following the [official DynamoDB Getting Started guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GettingStartedDynamoDB.html).

**Demonstrates:**
- Composite keys (partition key + sort key)
- CRUD operations
- Querying with sort key conditions
- Atomic updates
- Conditional writes

### [single_table_design.py](./single_table_design.py)
Single table design pattern using polymorphic models.

**Demonstrates:**
- Polymorphic models with `Discriminator`
- `@register` decorator
- Multiple entity types in one table (Customer, Order, Product)
- Efficient access patterns

### [gsi_examples.py](./gsi_examples.py)
Global Secondary Index demonstrations.

**Demonstrates:**
- Multiple GSIs on one model
- `GSIKey` and `GSISortKey` fields
- Querying different indexes
- Range queries on GSI sort keys

### [fastapi_integration/main.py](./fastapi_integration/main.py)
Minimal FastAPI application.

**Demonstrates:**
- Using Dynantic models as FastAPI response models
- CRUD endpoints
- Automatic OpenAPI documentation

**Run:**
```bash
cd fastapi_integration
pip install -r requirements.txt
uvicorn main:app --reload
# Visit http://localhost:8000/docs
```

## Notes

- Examples are educational code snippets, not production applications
- You'll need to create DynamoDB tables before running
- Use AWS credentials or LocalStack for testing
