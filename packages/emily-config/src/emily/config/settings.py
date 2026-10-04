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

    provider_timeout_seconds: float = Field(
        default=60.0,
        **_alias("EMILY_PROVIDER_TIMEOUT_SECONDS", "PROVIDER_TIMEOUT_SECONDS"),
    )
    provider_max_retries: int = Field(
        default=2,
        **_alias("EMILY_PROVIDER_MAX_RETRIES", "PROVIDER_MAX_RETRIES"),
    )
    provider_failover_enabled: bool = Field(
        default=True,
        **_alias("EMILY_PROVIDER_FAILOVER_ENABLED", "PROVIDER_FAILOVER_ENABLED"),
    )
    mission_llm_planner: bool = Field(
        default=True,
        **_alias("EMILY_MISSION_LLM_PLANNER", "MISSION_LLM_PLANNER"),
    )

    agent_max_concurrent: int = Field(
        default=8,
        **_alias("EMILY_AGENT_MAX_CONCURRENT", "AGENT_MAX_CONCURRENT"),
    )
    agent_pool_timeout_seconds: float = Field(
        default=30.0,
        **_alias("EMILY_AGENT_POOL_TIMEOUT_SECONDS", "AGENT_POOL_TIMEOUT_SECONDS"),
    )
    agent_llm_workers: bool = Field(
        default=True,
        **_alias("EMILY_AGENT_LLM_WORKERS", "AGENT_LLM_WORKERS"),
    )
    agent_llm_timeout_seconds: float = Field(
        default=45.0,
        **_alias("EMILY_AGENT_LLM_TIMEOUT_SECONDS", "AGENT_LLM_TIMEOUT_SECONDS"),
    )
    agent_history_enabled: bool = Field(
        default=True,
        **_alias("EMILY_AGENT_HISTORY_ENABLED", "AGENT_HISTORY_ENABLED"),
    )
    agent_history_directory: Path = Field(
        default=Path("data/agents"),
        **_alias("EMILY_AGENT_HISTORY_DIRECTORY", "AGENT_HISTORY_DIRECTORY"),
    )

    voice_enabled: bool = Field(default=False, **_alias("EMILY_VOICE_ENABLED", "VOICE_ENABLED"))
    wake_word: str = Field(default="Hey Emily", **_alias("EMILY_WAKE_WORD", "WAKE_WORD"))
    voice_wake_word_enabled: bool = Field(
        default=False,
        **_alias("EMILY_VOICE_WAKE_WORD_ENABLED", "VOICE_WAKE_WORD_ENABLED"),
    )
    voice_wake_word_threshold: float = Field(
        default=0.5,
        **_alias("EMILY_VOICE_WAKE_WORD_THRESHOLD", "VOICE_WAKE_WORD_THRESHOLD"),
    )
    voice_wake_word_model: Path | None = Field(
        default=None,
        **_alias("EMILY_VOICE_WAKE_WORD_MODEL", "VOICE_WAKE_WORD_MODEL"),
    )
    voice_wake_word_max_listen_s: float = Field(
        default=12.0,
        **_alias("EMILY_VOICE_WAKE_WORD_MAX_LISTEN_S", "VOICE_WAKE_WORD_MAX_LISTEN_S"),
    )
    voice_wake_word_listen_chunk_s: float = Field(
        default=7.5,
        **_alias("EMILY_VOICE_WAKE_WORD_LISTEN_CHUNK_S", "VOICE_WAKE_WORD_LISTEN_CHUNK_S"),
    )
    voice_listen_chunk_s: float = Field(
        default=10.0,
        **_alias("EMILY_VOICE_LISTEN_CHUNK_S", "VOICE_LISTEN_CHUNK_S"),
    )
    voice_ui_port: int = Field(
        default=8765,
        **_alias("EMILY_VOICE_UI_PORT", "VOICE_UI_PORT"),
    )
    voice_directory: Path = Field(
        default=Path("data/voice"),
        **_alias("EMILY_VOICE_DIRECTORY", "VOICE_DIRECTORY"),
    )
    voice_models_directory: Path = Field(
        default=Path("models/voice"),
        **_alias("EMILY_VOICE_MODELS_DIRECTORY", "VOICE_MODELS_DIRECTORY"),
    )
    voice_personality_path: Path | None = Field(
        default=None,
        **_alias("EMILY_VOICE_PERSONALITY_PATH", "VOICE_PERSONALITY_PATH"),
    )
    voice_register_tools: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_REGISTER_TOOLS", "VOICE_REGISTER_TOOLS"),
    )
    voice_streaming: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_STREAMING", "VOICE_STREAMING"),
    )
    voice_tts_stream_sentences: bool = Field(
        default=False,
        **_alias("EMILY_VOICE_TTS_STREAM_SENTENCES", "VOICE_TTS_STREAM_SENTENCES"),
    )
    voice_barge_in: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_BARGE_IN", "VOICE_BARGE_IN"),
    )
    voice_language_auto_detect: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_LANGUAGE_AUTO_DETECT", "VOICE_LANGUAGE_AUTO_DETECT"),
    )
    voice_code_switching: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_CODE_SWITCHING", "VOICE_CODE_SWITCHING"),
    )
    voice_emotion: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_EMOTION", "VOICE_EMOTION"),
    )
    voice_adaptive_pacing: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_ADAPTIVE_PACING", "VOICE_ADAPTIVE_PACING"),
    )
    voice_adaptive_pauses: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_ADAPTIVE_PAUSES", "VOICE_ADAPTIVE_PAUSES"),
    )
    voice_prefer_energy_vad: bool = Field(
        default=False,
        **_alias("EMILY_VOICE_PREFER_ENERGY_VAD", "VOICE_PREFER_ENERGY_VAD"),
    )
    voice_preload_models: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_PRELOAD_MODELS", "VOICE_PRELOAD_MODELS"),
    )
    voice_keep_models_warm: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_KEEP_MODELS_WARM", "VOICE_KEEP_MODELS_WARM"),
    )
    tts_default: str = Field(
        default="voicebox",
        **_alias("EMILY_TTS_DEFAULT", "TTS_DEFAULT"),
    )
    tts_enable_kokoro: bool = Field(
        default=True,
        **_alias("EMILY_TTS_ENABLE_KOKORO", "TTS_ENABLE_KOKORO"),
    )
    tts_enable_indicf5: bool = Field(
        default=False,
        **_alias("EMILY_TTS_ENABLE_INDICF5", "TTS_ENABLE_INDICF5"),
    )
    tts_enable_chatterbox: bool = Field(
        default=False,
        **_alias("EMILY_TTS_ENABLE_CHATTERBOX", "TTS_ENABLE_CHATTERBOX"),
    )
    tts_enable_voicebox: bool = Field(
        default=True,
        **_alias("EMILY_TTS_ENABLE_VOICEBOX", "TTS_ENABLE_VOICEBOX"),
    )
    voice_voicebox_url: str = Field(
        default="http://127.0.0.1:17493",
        **_alias("EMILY_VOICE_VOICEBOX_URL", "VOICE_VOICEBOX_URL"),
    )
    voice_voicebox_profile: str | None = Field(
        default="Emily",
        **_alias("EMILY_VOICE_VOICEBOX_PROFILE", "VOICE_VOICEBOX_PROFILE"),
    )
    voice_voicebox_client_id: str = Field(
        default="emily",
        **_alias("EMILY_VOICE_VOICEBOX_CLIENT_ID", "VOICE_VOICEBOX_CLIENT_ID"),
    )
    voice_voicebox_timeout_seconds: float = Field(
        default=90.0,
        **_alias("EMILY_VOICE_VOICEBOX_TIMEOUT_SECONDS", "VOICE_VOICEBOX_TIMEOUT_SECONDS"),
    )
    voice_voicebox_instruct: str | None = Field(
        default=(
            "Speak like a sweet young girl around eighteen — soft, warm, gentle, and slightly playful. "
            "Light bright tone, relaxed pace, never loud, mature, rushed, or panicky."
        ),
        **_alias("EMILY_VOICE_VOICEBOX_INSTRUCT", "VOICE_VOICEBOX_INSTRUCT"),
    )
    voice_voicebox_use_presets: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_VOICEBOX_USE_PRESETS", "VOICE_VOICEBOX_USE_PRESETS"),
    )
    voice_voicebox_engine: str = Field(
        default="auto",
        **_alias("EMILY_VOICE_VOICEBOX_ENGINE", "VOICE_VOICEBOX_ENGINE"),
    )
    voice_voicebox_personality: bool = Field(
        default=False,
        **_alias("EMILY_VOICE_VOICEBOX_PERSONALITY", "VOICE_VOICEBOX_PERSONALITY"),
    )
    voice_voicebox_preset_en: str = Field(
        default="Serena",
        **_alias("EMILY_VOICE_VOICEBOX_PRESET_EN", "VOICE_VOICEBOX_PRESET_EN"),
    )
    voice_voicebox_preset_kokoro_en: str = Field(
        default="af_bella",
        **_alias("EMILY_VOICE_VOICEBOX_PRESET_KOKORO_EN", "VOICE_VOICEBOX_PRESET_KOKORO_EN"),
    )
    voice_voicebox_preset_kokoro_hi: str = Field(
        default="hf_beta",
        **_alias("EMILY_VOICE_VOICEBOX_PRESET_KOKORO_HI", "VOICE_VOICEBOX_PRESET_KOKORO_HI"),
    )
    tts_device: str = Field(
        default="auto",
        **_alias("EMILY_TTS_DEVICE", "TTS_DEVICE"),
    )
    voice_tts_prefer_lightweight: bool = Field(
        default=False,
        **_alias("EMILY_VOICE_TTS_PREFER_LIGHTWEIGHT", "VOICE_TTS_PREFER_LIGHTWEIGHT"),
    )
    voice_llm_timeout_seconds: float = Field(
        default=45.0,
        **_alias("EMILY_VOICE_LLM_TIMEOUT_SECONDS", "VOICE_LLM_TIMEOUT_SECONDS"),
    )
    voice_mic_min_rms: float = Field(
        default=0.001,
        **_alias("EMILY_VOICE_MIC_MIN_RMS", "VOICE_MIC_MIN_RMS"),
    )
    voice_wake_max_attempts: int = Field(
        default=15,
        **_alias("EMILY_VOICE_WAKE_MAX_ATTEMPTS", "VOICE_WAKE_MAX_ATTEMPTS"),
    )
    voice_asr_model: str = Field(
        default="base",
        **_alias("EMILY_VOICE_ASR_MODEL", "VOICE_ASR_MODEL"),
    )
    voice_asr_language: str | None = Field(
        default=None,
        **_alias("EMILY_VOICE_ASR_LANGUAGE", "VOICE_ASR_LANGUAGE"),
    )
    voice_bangla_asr_enabled: bool = Field(
        default=True,
        **_alias("EMILY_VOICE_BANGLA_ASR_ENABLED", "VOICE_BANGLA_ASR_ENABLED"),
    )
    voice_bangla_asr_model: str = Field(
        default="bangla-speech-processing/BanglaASR",
        **_alias("EMILY_VOICE_BANGLA_ASR_MODEL", "VOICE_BANGLA_ASR_MODEL"),
    )
    voice_indicf5_ref_audio: Path | None = Field(
        default=None,
        **_alias("EMILY_VOICE_INDICF5_REF_AUDIO", "VOICE_INDICF5_REF_AUDIO"),
    )
    voice_indicf5_ref_text: str = Field(
        default="",
        **_alias("EMILY_VOICE_INDICF5_REF_TEXT", "VOICE_INDICF5_REF_TEXT"),
    )
    memory_enabled: bool = Field(default=True, **_alias("EMILY_MEMORY_ENABLED", "MEMORY_ENABLED"))
    memory_directory: Path = Field(
        default=Path("data/memory"),
        **_alias("EMILY_MEMORY_DIRECTORY", "MEMORY_DIRECTORY"),
    )
    world_directory: Path = Field(
        default=Path("data/world"),
        **_alias("EMILY_WORLD_DIRECTORY", "WORLD_DIRECTORY"),
    )
    memory_retrieval_limit: int = Field(
        default=8,
        **_alias("EMILY_MEMORY_RETRIEVAL_LIMIT", "MEMORY_RETRIEVAL_LIMIT"),
    )
    tools_enabled: bool = Field(
        default=True,
        **_alias("EMILY_TOOLS_ENABLED", "TOOLS_ENABLED"),
    )
    tool_timeout_seconds: float = Field(
        default=15.0,
        **_alias("EMILY_TOOL_TIMEOUT_SECONDS", "TOOL_TIMEOUT_SECONDS"),
    )
    tool_allow_execute: bool = Field(
        default=True,
        **_alias("EMILY_TOOL_ALLOW_EXECUTE", "TOOL_ALLOW_EXECUTE"),
    )
    allow_network: bool = Field(
        default=False,
        **_alias("EMILY_ALLOW_NETWORK", "ALLOW_NETWORK"),
    )
    mcp_catalog_path: Path = Field(
        default=Path("data/mcp/catalog.json"),
        **_alias("EMILY_MCP_CATALOG_PATH", "MCP_CATALOG_PATH"),
    )
    chat_history_directory: Path = Field(
        default=Path("data/history"),
        **_alias("EMILY_CHAT_HISTORY_DIRECTORY", "CHAT_HISTORY_DIRECTORY"),
    )
    vision_enabled: bool = Field(default=False, **_alias("EMILY_VISION_ENABLED", "VISION_ENABLED"))
    ocr_enabled: bool = Field(default=False, **_alias("EMILY_OCR_ENABLED", "OCR_ENABLED"))
    desktop_enabled: bool = Field(
        default=True,
        **_alias("EMILY_DESKTOP_ENABLED", "DESKTOP_ENABLED"),
    )
    desktop_control: bool = Field(
        default=False,
        **_alias("EMILY_DESKTOP_CONTROL", "DESKTOP_CONTROL"),
    )
    desktop_live: bool = Field(
        default=True,
        **_alias("EMILY_DESKTOP_LIVE", "DESKTOP_LIVE"),
    )
    desktop_powershell_enabled: bool = Field(
        default=False,
        **_alias("EMILY_DESKTOP_POWERSHELL", "DESKTOP_POWERSHELL"),
    )
    desktop_registry_enabled: bool = Field(
        default=True,
        **_alias("EMILY_DESKTOP_REGISTRY", "DESKTOP_REGISTRY"),
    )
    desktop_registry_write: bool = Field(
        default=False,
        **_alias("EMILY_DESKTOP_REGISTRY_WRITE", "DESKTOP_REGISTRY_WRITE"),
    )
    desktop_register_tools: bool = Field(
        default=True,
        **_alias("EMILY_DESKTOP_REGISTER_TOOLS", "DESKTOP_REGISTER_TOOLS"),
    )
    desktop_registry_allow_prefixes: list[str] = Field(
        default_factory=lambda: [
            "HKCU\\Software\\EmilyOS",
            "HKCU\\Software\\Emily",
        ],
        **_alias("EMILY_DESKTOP_REGISTRY_ALLOW_PREFIXES", "DESKTOP_REGISTRY_ALLOW_PREFIXES"),
    )
    browser_enabled: bool = Field(
        default=True,
        **_alias("EMILY_BROWSER_ENABLED", "BROWSER_ENABLED"),
    )
    browser_automation: bool = Field(
        default=False,
        **_alias("EMILY_BROWSER_AUTOMATION", "BROWSER_AUTOMATION"),
    )
    browser_headless: bool = Field(
        default=True,
        **_alias("EMILY_BROWSER_HEADLESS", "BROWSER_HEADLESS"),
    )
    browser_default_profile: str = Field(
        default="default",
        **_alias("EMILY_BROWSER_PROFILE", "BROWSER_PROFILE"),
    )
    browser_profiles_directory: Path = Field(
        default=Path("data/browser/profiles"),
        **_alias("EMILY_BROWSER_PROFILES_DIRECTORY", "BROWSER_PROFILES_DIRECTORY"),
    )
    browser_register_tools: bool = Field(
        default=True,
        **_alias("EMILY_BROWSER_REGISTER_TOOLS", "BROWSER_REGISTER_TOOLS"),
    )
    browser_channel: str | None = Field(
        default=None,
        **_alias("EMILY_BROWSER_CHANNEL", "BROWSER_CHANNEL"),
    )
    browser_url_allow_prefixes: list[str] = Field(
        default_factory=list,
        **_alias("EMILY_BROWSER_URL_ALLOW_PREFIXES", "BROWSER_URL_ALLOW_PREFIXES"),
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
            "allow_network": self.allow_network,
            "confirm_destructive_actions": self.confirm_destructive_actions,
            "desktop_enabled": self.desktop_enabled,
            "desktop_control": self.desktop_control,
            "desktop_live": self.desktop_live,
            "browser_enabled": self.browser_enabled,
            "browser_automation": self.browser_automation,
            "voice_enabled": self.voice_enabled,
            "tool_allow_execute": self.tool_allow_execute,
        }
