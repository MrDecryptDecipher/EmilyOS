from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str
    APP_VERSION: str

    ENVIRONMENT: str

    LOG_LEVEL: str

    PRIMARY_PROVIDER: str

    NVIDIA_API_KEY: str
    NVIDIA_BASE_URL: str
    NVIDIA_MODEL: str

    BACKUP_PROVIDER: str

    ROUTESME_API_KEY: str
    ROUTESME_BASE_URL: str
    ROUTESME_MODEL: str

    VOICE_ENABLED: bool

    WAKE_WORD: str

    MEMORY_ENABLED: bool

    MEMORY_DIRECTORY: str

    CHAT_HISTORY_DIRECTORY: str

    VISION_ENABLED: bool

    OCR_ENABLED: bool

    DESKTOP_CONTROL: bool

    BROWSER_AUTOMATION: bool

    ALLOW_TERMINAL: bool

    ALLOW_FILE_WRITE: bool

    ALLOW_BROWSER: bool

    ALLOW_SYSTEM_COMMANDS: bool

    CONFIRM_DESTRUCTIVE_ACTIONS: bool

    DEBUG: bool


settings = Settings()