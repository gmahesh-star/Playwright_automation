"""Application configuration via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database (SQLite — local file, no server required) ─────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./playwright_platform.db"
    DB_ECHO: bool = False

    # ── Redis ───────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Artifact storage ────────────────────────────────────────────────
    ARTIFACTS_DIR: Path = Path("artifacts")

    @property
    def traces_dir(self) -> Path:
        path = self.ARTIFACTS_DIR / "traces"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def videos_dir(self) -> Path:
        path = self.ARTIFACTS_DIR / "videos"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def screenshots_dir(self) -> Path:
        path = self.ARTIFACTS_DIR / "screenshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def auth_states_dir(self) -> Path:
        path = self.ARTIFACTS_DIR / "auth_states"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ── Playwright defaults ─────────────────────────────────────────────
    DEFAULT_BROWSER: Literal["chromium", "firefox", "webkit"] = "chromium"
    DEFAULT_TIMEOUT_MS: int = 30_000
    HEADLESS: bool = True

    # ── Visual regression ───────────────────────────────────────────────
    VISUAL_DIFF_THRESHOLD: float = 0.1  # 0.0–1.0, fraction of differing pixels

    # ── Server ──────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False


settings = Settings()
