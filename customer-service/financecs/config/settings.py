from pathlib import Path

from pydantic_settings import SettingsConfigDict, BaseSettings

PROJECT_DIR = Path(__file__).resolve().parents[2]

ENV_FILE_PATH = PROJECT_DIR / ".env"


class Settings(BaseSettings):
    # ===== LLM =====
    llm_model: str
    llm_base_url: str
    llm_api_key: str

    # ===== 应用 =====
    app_host: str
    app_port: int
    session_idle_timeout_minutes: int = 30

    # ===== 金融业务中台 =====
    finance_api_base_url: str
    finance_api_channel_code: str = "AI_CS"
    finance_api_timeout_connect: int = 5
    finance_api_timeout_read: int = 30
    finance_api_max_retries: int = 2

    # ===== 客服对话状态库 =====
    cs_database_url: str
    cs_db_echo: bool = False

    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, env_file_encoding="utf-8")


settings = Settings()  # type:ignore
