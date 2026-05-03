"""Load environment variables and provide a Settings object."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_dotenv_files() -> None:
    for filename in (".env.local", ".env"):
        path = Path(filename)
        if path.exists():
            load_dotenv(path, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: Literal["local", "dev", "prod"] = Field(
        default="local", validation_alias=AliasChoices("APP_ENV")
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
    gemini_validation_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GEMINI_VALIDATION_API_KEY")
    )
    gemini_validation_model: str | None = Field(
        default=None, validation_alias=AliasChoices("GEMINI_VALIDATION_MODEL")
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
    openrouter_validation_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENROUTER_VALIDATION_API_KEY")
    )
    openrouter_validation_model: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENROUTER_VALIDATION_MODEL")
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
    openai_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY")
    )
    openai_model: str = Field(
        default="gpt-4o-mini", validation_alias=AliasChoices("OPENAI_MODEL")
    )
    openai_validation_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_VALIDATION_API_KEY")
    )
    openai_validation_model: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_VALIDATION_MODEL")
    )
    openai_temperature: float = Field(
        default=0.3, validation_alias=AliasChoices("OPENAI_TEMPERATURE")
    )
    openai_max_tokens: int = Field(
        default=1024, validation_alias=AliasChoices("OPENAI_MAX_TOKENS")
    )
    anthropic_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY")
    )
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20240620",
        validation_alias=AliasChoices("ANTHROPIC_MODEL"),
    )
    anthropic_validation_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_VALIDATION_API_KEY")
    )
    anthropic_validation_model: str | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_VALIDATION_MODEL")
    )
    anthropic_temperature: float = Field(
        default=0.3, validation_alias=AliasChoices("ANTHROPIC_TEMPERATURE")
    )
    anthropic_max_tokens: int = Field(
        default=1024, validation_alias=AliasChoices("ANTHROPIC_MAX_TOKENS")
    )
    judge_providers: str = Field(
        default="", validation_alias=AliasChoices("JUDGE_PROVIDERS")
    )

    frontend_url: str = Field(
        default="http://localhost:3000", validation_alias=AliasChoices("FRONTEND_URL")
    )
    backend_public_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("BACKEND_PUBLIC_URL"),
    )
    enable_provider_validation_integrations: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_PROVIDER_VALIDATION_INTEGRATIONS"),
    )
    validation_callback_signing_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VALIDATION_CALLBACK_SIGNING_SECRET"),
    )
    validation_callback_ttl_seconds: int = Field(
        default=900,
        validation_alias=AliasChoices("VALIDATION_CALLBACK_TTL_SECONDS"),
    )
    openai_mcp_launch_url: str = Field(
        default="https://chatgpt.com/",
        validation_alias=AliasChoices("OPENAI_MCP_LAUNCH_URL"),
    )
    gemini_function_launch_url: str = Field(
        default="https://gemini.google.com/",
        validation_alias=AliasChoices("GEMINI_FUNCTION_LAUNCH_URL"),
    )
    clerk_webhook_secret: str | None = Field(
        default=None, validation_alias=AliasChoices("CLERK_WEBHOOK_SECRET")
    )
    agent_principal_signing_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AGENT_PRINCIPAL_SIGNING_SECRET"),
    )
    registry_approval_signing_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REGISTRY_APPROVAL_SIGNING_SECRET"),
    )
    admin_user_ids: str = Field(
        default="", validation_alias=AliasChoices("ADMIN_USER_IDS")
    )


_load_dotenv_files()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
