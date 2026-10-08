"""Configuración de la aplicación, leída de variables de entorno y `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# `.env` vive en la raíz del monorepo. Sin Docker, el backend se ejecuta desde
# `backend/`; con Docker Compose las variables llegan ya por `env_file`.
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
ENV_FILES = (_REPO_ROOT_ENV, Path(".env"))

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        # `.env` también contiene variables solo de Docker Compose (puertos).
        extra="ignore",
    )

    environment: Environment = "development"
    log_level: LogLevel = "INFO"

    # Base de datos
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    db_echo: bool = False

    # Autenticación
    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    refresh_cookie_secure: bool = True

    # CORS: lista JSON de orígenes explícitos.
    cors_origins: list[str] = Field(default_factory=list)

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_origin(cls, origins: list[str]) -> list[str]:
        # Con credenciales (cookie de refresh) nunca se admite "*".
        if "*" in origins:
            raise ValueError("CORS_ORIGINS no puede contener '*'")
        return [origin.rstrip("/") for origin in origins]

    @model_validator(mode="after")
    def _check_production_safety(self) -> Self:
        if self.environment != "production":
            return self
        secret = self.jwt_secret_key.get_secret_value()
        if secret.startswith("change-me") or len(secret) < 32:
            raise ValueError("JWT_SECRET_KEY debe ser aleatoria y de al menos 32 caracteres")
        if self.postgres_password.get_secret_value().startswith("change-me"):
            raise ValueError("POSTGRES_PASSWORD conserva el valor de ejemplo")
        if not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SECURE debe ser true en producción")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
