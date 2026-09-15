"""Non-secret provider configuration status models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ProviderStatusResponse(BaseModel):
    """Safe configuration summary for a UI or operator status panel."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    region: str
    credential_mode: Literal[
        "stub", "bearer_token", "session_bearer_token", "aws_default_chain"
    ]
    max_output_tokens: int = Field(ge=1)
    max_report_chars: int = Field(ge=1)
    max_drafts_per_task: int = Field(ge=0)


class ProviderSessionCreate(BaseModel):
    """Loopback-only request for a short-lived in-memory provider session."""

    model_config = ConfigDict(extra="forbid")

    bearer_token: SecretStr
    ttl_seconds: int = Field(default=3600, ge=60, le=43_200)
