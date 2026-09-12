"""Small, deterministic guards shared by untrusted adapters."""

from collections.abc import Iterable


class BoundaryViolation(ValueError):
    """An external input or capability request is outside the adapter contract."""


def validate_untrusted_text(value: str, *, max_characters: int) -> str:
    """Validate text as data; reject control bytes and enforce a hard bound."""
    if not isinstance(value, str) or not value.strip():
        raise BoundaryViolation("External text must be non-empty")
    if len(value) > max_characters:
        raise BoundaryViolation("External text exceeds the configured limit")
    if "\x00" in value or any(ord(char) < 9 and char not in "\n\r\t" for char in value):
        raise BoundaryViolation("External text contains control characters")
    return value


def data_delimit(value: str, *, label: str = "UNTRUSTED_DATA") -> str:
    """Place untrusted material in an explicit data-only envelope for providers."""
    safe_label = "".join(char for char in label.upper() if char.isalnum() or char == "_")
    safe_label = safe_label or "UNTRUSTED_DATA"
    return f"BEGIN_{safe_label}\n{value}\nEND_{safe_label}"


def require_capability(requested: str, allowed: Iterable[str]) -> str:
    """Allow only an explicitly granted capability name."""
    if requested not in set(allowed):
        raise BoundaryViolation("Capability is not permitted")
    return requested
