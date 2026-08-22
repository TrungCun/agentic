from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

_APP_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _APP_DIR.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT.parent / ".env", _REPO_ROOT / ".env", _APP_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix=""
    )

    # --- LLM Configurations ---
    llm_base_url: str = Field(...)
    llm_model: str = Field(...)
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096


settings = Settings()
