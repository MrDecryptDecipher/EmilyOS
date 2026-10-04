"""Plugin Manifest schema definition (emily-plugin.json)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    entrypoint: str = "main.py"
    permissions: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
