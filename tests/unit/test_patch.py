"""
Unit tests for the patch method and UpdateBuilder.
"""

from dynantic import DynamoModel, Key, SortKey
from dynantic.updates import Add, Delete, Remove, Set, UpdateBuilder


class TestPatchMethod:
    """Test DynamoModel.patch() method."""

    def test_patch_initialization_pk_only(self):
        """Test that patch() initializes UpdateBuilder with correct PK."""

        class User(DynamoModel):
            class Meta:
                table_name = "users"
                pk_name = "email"

            email: str = Key()
            name: str

        user = User(email="test@example.com", name="Test User")
        builder = user.patch()

        assert isinstance(builder, UpdateBuilder)
        assert builder.pk == "test@example.com"
        assert builder.sk is None
        assert builder.model_cls == User

    def test_patch_initialization_pk_sk(self):
        """Test that patch() initializes UpdateBuilder with correct PK and SK."""

        class Log(DynamoModel):
            class Meta:
                table_name = "logs"
                pk_name = "group"
                sk_name = "timestamp"

            group: str = Key()
            timestamp: int = SortKey()
            message: str

        log = Log(group="error-logs", timestamp=1234567890, message="Critical error")
        builder = log.patch()

        assert isinstance(builder, UpdateBuilder)
        assert builder.pk == "error-logs"
        assert builder.sk == 1234567890
        assert builder.model_cls == Log


class TestUpdateBuilderReflected:
    """Test UpdateBuilder logic without DB calls (reflected in actions)."""

    class User(DynamoModel):
        class Meta:
            table_name = "users"

        id: str = Key()
        name: str
        age: int = 0
        roles: set[str] = set()
        score: float = 0.0

    def test_set_action(self):
        builder = UpdateBuilder(self.User, "123")
        builder.set(self.User.name, "New Name")
        assert len(builder.actions) == 1
        assert isinstance(builder.actions[0], Set)
        assert builder.actions[0].field_name == "name"
        assert builder.actions[0].value == "New Name"

    def test_add_action(self):
        builder = UpdateBuilder(self.User, "123")
        builder.add(self.User.age, 1)
        assert len(builder.actions) == 1
        assert isinstance(builder.actions[0], Add)
        assert builder.actions[0].field_name == "age"
        assert builder.actions[0].value == 1

    def test_remove_action(self):
        builder = UpdateBuilder(self.User, "123")
        builder.remove(self.User.name)
        assert len(builder.actions) == 1
        assert isinstance(builder.actions[0], Remove)
        assert builder.actions[0].field_name == "name"

    def test_delete_action(self):
        builder = UpdateBuilder(self.User, "123")
        builder.delete(self.User.roles, {"admin"})
        assert len(builder.actions) == 1
        assert isinstance(builder.actions[0], Delete)
        assert builder.actions[0].field_name == "roles"
        assert builder.actions[0].value == {"admin"}

    def test_chaining(self):
        builder = UpdateBuilder(self.User, "123")
        builder.set(self.User.name, "A").add(self.User.age, 1)
        assert len(builder.actions) == 2
