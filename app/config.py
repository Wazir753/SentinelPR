"""Single source of truth for environment configuration."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    log_level: str = "INFO"

    # GitHub App (Phase 3)
    github_app_id: str = ""
    github_app_private_key_path: str = ""
    github_webhook_secret: str = ""

    # Hugging Face Inference API (Phase 2)
    hf_api_token: str = ""

    # Outbound notifications (Phase 3+)
    notify_webhook_url: str = ""

    # Retrieval / vector store (Phase 1)
    chroma_persist_dir: Path = PROJECT_ROOT / "data" / "chroma"
    repo_clone_dir: Path = PROJECT_ROOT / "data" / "repos"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    @field_validator("chroma_persist_dir", "repo_clone_dir", mode="before")
    @classmethod
    def default_path_if_empty(cls, value: str | Path | None, info) -> Path:
        defaults = {
            "chroma_persist_dir": PROJECT_ROOT / "data" / "chroma",
            "repo_clone_dir": PROJECT_ROOT / "data" / "repos",
        }
        if value is None or value == "":
            return defaults[info.field_name]
        return Path(value)

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "dev", "local"}


settings = Settings()
