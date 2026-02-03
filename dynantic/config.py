from dataclasses import dataclass, field
from typing import Any


@dataclass
class GSIDefinition:
    """
    Represents a Global Secondary Index definition.

    Contains the metadata needed to query and scan a GSI,
    including the partition key and optional sort key field names.
    """

    index_name: str
    pk_name: str
    pk_type: str = "S"
    sk_name: str | None = None
    sk_type: str = "S"
    projection_type: str = "ALL"


@dataclass
class ModelOptions:
    """
    Internal container for Model metadata.
    Populated by the Metaclass during class creation.
    """

    table_name: str
    pk_name: str
    sk_name: str | None = None
    region: str = "us-east-1"
    gsi_definitions: dict[str, GSIDefinition] = field(default_factory=dict)

    # Polymorphism support
    discriminator_field: str | None = None  # Name of the discriminator field
    entity_registry: dict[str, Any] = field(
        default_factory=dict
    )  # discriminator_value -> entity_class
    is_base_entity: bool = False  # True if this model has a discriminator
    parent_model: Any | None = None  # Reference to base class for subclasses
    discriminator_value: str | None = None  # The discriminator value for this subclass

    def get_gsi(self, index_name: str) -> GSIDefinition | None:
        """
        Get a GSI definition by index name.

        Args:
            index_name: Name of the GSI to retrieve

        Returns:
            GSIDefinition if found, None otherwise
        """
        return self.gsi_definitions.get(index_name)

    def has_gsi(self, index_name: str) -> bool:
        """
        Check if a GSI exists on this model.

        Args:
            index_name: Name of the GSI to check

        Returns:
            True if the GSI exists, False otherwise
        """
        return index_name in self.gsi_definitions

    def is_polymorphic(self) -> bool:
        """
        Check if this model supports polymorphism.

        Returns:
            True if the model has a discriminator field, False otherwise
        """
        return self.discriminator_field is not None

    def get_entity_class(self, discriminator_value: str) -> Any | None:
        """
        Get the entity class for a discriminator value.

        Args:
            discriminator_value: The discriminator value to look up

        Returns:
            The entity class if found, None otherwise
        """
        return self.entity_registry.get(discriminator_value)

    def register_entity(self, discriminator_value: str, entity_class: Any) -> None:
        """
        Register an entity class for a discriminator value.

        Args:
            discriminator_value: The discriminator value
            entity_class: The entity class to register

        Raises:
            ValueError: If the discriminator value is already registered
        """
        if discriminator_value in self.entity_registry:
            existing = self.entity_registry[discriminator_value]
            raise ValueError(
                f"Discriminator value '{discriminator_value}' is already registered "
                f"to {existing.__name__}, cannot register {entity_class.__name__}"
            )
        self.entity_registry[discriminator_value] = entity_class
