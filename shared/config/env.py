"""Load environment variables and provide a Settings object."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


def _load_dotenv_files() -> None:
    for filename in (".env.local", ".env"):
        path = Path(filename)
        if path.exists():
            load_dotenv(path, override=False)


class Settings(BaseSettings):
    app_env: Literal["local", "dev", "prod"] = Field(
        default="local", validation_alias=AliasChoices("APP_ENV")
    )
    catalog_source: str = Field(
        default="mock", validation_alias=AliasChoices("CATALOG_SOURCE")
    )
    google_merchant_feed_path: str | None = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_MERCHANT_FEED_PATH")
    )
    shopify_domain: str | None = Field(
        default=None, validation_alias=AliasChoices("SHOPIFY_DOMAIN")
    )
    shopify_token: str | None = Field(
        default=None, validation_alias=AliasChoices("SHOPIFY_TOKEN")
    )

    database_path: str = Field(
        default="./tmp/local.db", validation_alias=AliasChoices("DATABASE_PATH")
    )

    llm_provider: str = Field(
        default="openrouter", validation_alias=AliasChoices("LLM_PROVIDER")
    )
    gemini_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY")
    )
    gemini_model: str = Field(
        default="gemini-3-pro-preview", validation_alias=AliasChoices("GEMINI_MODEL")
    )
    gemini_fallback_model: str = Field(
        default="gemini-2.0-flash",
        validation_alias=AliasChoices("GEMINI_FALLBACK_MODEL"),
    )
    openrouter_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENROUTER_API_KEY")
    )
    openrouter_model: str = Field(
        default="meta-llama/Meta-Llama-3-8B-Instruct",
        validation_alias=AliasChoices("OPENROUTER_MODEL"),
    )
    openrouter_temperature: float = Field(
        default=0.3, validation_alias=AliasChoices("OPENROUTER_TEMPERATURE")
    )
    openrouter_max_tokens: int = Field(
        default=1024, validation_alias=AliasChoices("OPENROUTER_MAX_TOKENS")
    )
    openrouter_site_url: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENROUTER_SITE_URL")
    )
    openrouter_app_name: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENROUTER_APP_NAME")
    )

    frontend_url: str = Field(
        default="http://localhost:3000", validation_alias=AliasChoices("FRONTEND_URL")
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


_load_dotenv_files()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
