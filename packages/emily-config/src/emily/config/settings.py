"""Typed Emily OS settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _alias(*names: str) -> dict[str, object]:
    # validation_alias as first match across env names
    from pydantic import AliasChoices

    return {"validation_alias": AliasChoices(*names)}


class EmilySettings(BaseSettings):
    """Production configuration surface for the platform spine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = Field(default="Emily OS", **_alias("EMILY_APP_NAME", "APP_NAME"))
    app_version: str = Field(default="0.1.0", **_alias("EMILY_APP_VERSION", "APP_VERSION"))
    environment: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        **_alias("EMILY_ENVIRONMENT", "ENVIRONMENT"),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        **_alias("EMILY_LOG_LEVEL", "LOG_LEVEL"),
    )
    debug: bool = Field(default=False, **_alias("EMILY_DEBUG", "DEBUG"))

    primary_provider: str = Field(
        default="nvidia",
        **_alias("EMILY_PRIMARY_PROVIDER", "PRIMARY_PROVIDER"),
    )
    backup_provider: str = Field(
        default="routesme",
        **_alias("EMILY_BACKUP_PROVIDER", "BACKUP_PROVIDER"),
    )

    nvidia_api_key: SecretStr = Field(
        default=SecretStr(""),
        **_alias("EMILY_NVIDIA_API_KEY", "NVIDIA_API_KEY"),
    )
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        **_alias("EMILY_NVIDIA_BASE_URL", "NVIDIA_BASE_URL"),
    )
    nvidia_model: str = Field(
        default="z-ai/glm-5.2",
        **_alias("EMILY_NVIDIA_MODEL", "NVIDIA_MODEL"),
    )

    routesme_api_key: SecretStr = Field(
        default=SecretStr(""),
        **_alias("EMILY_ROUTESME_API_KEY", "ROUTESME_API_KEY"),
    )
    routesme_base_url: str = Field(
        default="https://routesme.online/v1",
        **_alias("EMILY_ROUTESME_BASE_URL", "ROUTESME_BASE_URL"),
    )
    routesme_model: str = Field(
        default="DeepSeek-V4-Flash-0731",
        **_alias("EMILY_ROUTESME_MODEL", "ROUTESME_MODEL"),
    )

    voice_enabled: bool = Field(default=True, **_alias("EMILY_VOICE_ENABLED", "VOICE_ENABLED"))
    wake_word: str = Field(default="Emily", **_alias("EMILY_WAKE_WORD", "WAKE_WORD"))
    memory_enabled: bool = Field(default=True, **_alias("EMILY_MEMORY_ENABLED", "MEMORY_ENABLED"))
    memory_directory: Path = Field(
        default=Path("data/memory"),
        **_alias("EMILY_MEMORY_DIRECTORY", "MEMORY_DIRECTORY"),
    )
    chat_history_directory: Path = Field(
        default=Path("data/history"),
        **_alias("EMILY_CHAT_HISTORY_DIRECTORY", "CHAT_HISTORY_DIRECTORY"),
    )
    vision_enabled: bool = Field(default=True, **_alias("EMILY_VISION_ENABLED", "VISION_ENABLED"))
    ocr_enabled: bool = Field(default=True, **_alias("EMILY_OCR_ENABLED", "OCR_ENABLED"))
    desktop_control: bool = Field(
        default=False,
        **_alias("EMILY_DESKTOP_CONTROL", "DESKTOP_CONTROL"),
    )
    browser_automation: bool = Field(
        default=False,
        **_alias("EMILY_BROWSER_AUTOMATION", "BROWSER_AUTOMATION"),
    )

    allow_terminal: bool = Field(default=False, **_alias("EMILY_ALLOW_TERMINAL", "ALLOW_TERMINAL"))
    allow_file_write: bool = Field(
        default=False,
        **_alias("EMILY_ALLOW_FILE_WRITE", "ALLOW_FILE_WRITE"),
    )
    allow_browser: bool = Field(default=False, **_alias("EMILY_ALLOW_BROWSER", "ALLOW_BROWSER"))
    allow_system_commands: bool = Field(
        default=False,
        **_alias("EMILY_ALLOW_SYSTEM_COMMANDS", "ALLOW_SYSTEM_COMMANDS"),
    )
    confirm_destructive_actions: bool = Field(
        default=True,
        **_alias("EMILY_CONFIRM_DESTRUCTIVE_ACTIONS", "CONFIRM_DESTRUCTIVE_ACTIONS"),
    )

    @field_validator("primary_provider", "backup_provider")
    @classmethod
    def _normalize_provider(cls, value: str) -> str:
        return value.strip().lower()

    def provider_summary(self) -> dict[str, str]:
        return {
            "primary": self.primary_provider,
            "backup": self.backup_provider,
            "nvidia_model": self.nvidia_model,
            "routesme_model": self.routesme_model,
        }

    def security_summary(self) -> dict[str, bool]:
        return {
            "allow_terminal": self.allow_terminal,
            "allow_file_write": self.allow_file_write,
            "allow_browser": self.allow_browser,
            "allow_system_commands": self.allow_system_commands,
            "confirm_destructive_actions": self.confirm_destructive_actions,
            "desktop_control": self.desktop_control,
            "browser_automation": self.browser_automation,
        }
