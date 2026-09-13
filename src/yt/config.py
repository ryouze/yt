from typing import ClassVar

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    App-wide settings read from environment variables.

    Attributes:
        refresh_interval_seconds (int): How often to refresh the list of available videos, in seconds (default: 900).
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        # Reject inputs that require implicit type coercion
        strict=True,
        # Prevent settings from being mutated after construction
        frozen=True,
        # Disallow arbitrary non-Pydantic types
        arbitrary_types_allowed=False,
        # Treat empty environment variables as missing
        env_ignore_empty=True,
        # `extra="forbid"` and `validate_default=True` are already enabled by default
    )

    refresh_interval_seconds: PositiveInt = 900


settings = Settings()
