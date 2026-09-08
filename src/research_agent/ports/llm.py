"""Provider-neutral interface for structured LLM operations."""

from typing import Protocol

from pydantic import BaseModel


class StructuredLLM(Protocol):
    """Generate validated structured output from a provider."""

    def generate(self, prompt: str, output_model: type[BaseModel]) -> BaseModel:
        """Generate one response without exposing provider credentials to callers."""
