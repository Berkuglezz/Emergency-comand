from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_BASE: dict[str, Any] = {
    "postgres_user": "user",
    "postgres_password": "change-me-db-password",
    "postgres_db": "db",
    "jwt_secret_key": "change-me-generate-a-random-64-char-hex-string",
}


def _settings(**overrides: Any) -> Settings:
    # Sin `.env`: solo cuentan los valores del test.
    return Settings(_env_file=None, **{**_BASE, **overrides})


def test_development_accepts_example_values() -> None:
    settings = _settings(environment="development", refresh_cookie_secure=False)
    assert settings.is_development


def test_cors_rejects_wildcard() -> None:
    with pytest.raises(ValidationError):
        _settings(cors_origins=["*"])


def test_cors_normalizes_trailing_slash() -> None:
    settings = _settings(cors_origins=["http://localhost:5173/"])
    assert settings.cors_origins == ["http://localhost:5173"]


def test_production_rejects_example_secret() -> None:
    with pytest.raises(ValidationError):
        _settings(environment="production", postgres_password="a-real-password")


def test_production_rejects_insecure_cookie() -> None:
    with pytest.raises(ValidationError):
        _settings(
            environment="production",
            postgres_password="a-real-password",
            jwt_secret_key="x" * 64,
            refresh_cookie_secure=False,
        )


def test_production_accepts_safe_values() -> None:
    settings = _settings(
        environment="production",
        postgres_password="a-real-password",
        jwt_secret_key="x" * 64,
        refresh_cookie_secure=True,
    )
    assert not settings.is_development
