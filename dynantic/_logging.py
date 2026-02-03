import hashlib
import logging
from typing import Any

# Create the library logger
logger = logging.getLogger("dynantic")

# Add NullHandler to prevent "No handlers could be found" warnings
# if the application doesn't configure logging.
logger.addHandler(logging.NullHandler())


def redact_key(key: dict[str, Any] | str) -> str:
    """
    Redacts sensitive key information for logging.
    hashes the values to allow correlation without revealing PII.
    """
    try:
        if isinstance(key, dict):
            # Create a deterministic string representation of the key for hashing
            # We sort keys to ensure consistency
            redacted = {}
            for k, v in key.items():
                val_str = str(v).encode("utf-8")
                redacted[k] = hashlib.sha256(val_str).hexdigest()[:8]
            return str(redacted)
        else:
            # Hash single value keys
            return hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:8]
    except Exception:
        return "<redaction_failed>"
