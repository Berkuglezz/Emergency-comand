"""Configuración de logging con redacción de datos sensibles.

Ningún log debe contener contraseñas, tokens ni cookies (CLAUDE.md §6). El
filtro de redacción se aplica a todos los handlers como red de seguridad; aun
así, el código no debe pasar nunca esos valores a un logger.
"""

import logging
import logging.config
import re

REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = (
    r"password|passwd|secret|token|access_token|refresh_token|authorization|cookie|set-cookie"
)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Esquemas de autorización: "Bearer eyJ...", "Basic dXNl..."
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9\-._~+/]+=*"), rf"\1 {REDACTED}"),
    # JWT sueltos (tres segmentos base64url).
    (re.compile(r"\beyJ[\w-]*\.[\w-]+\.[\w-]+"), REDACTED),
    # Pares clave=valor / clave: valor / "clave": "valor".
    (
        re.compile(rf"""(?i)(["']?(?:{_SENSITIVE_KEYS})["']?\s*[:=]\s*)(["']?)[^\s"',;&}}]+\2"""),
        rf"\1\2{REDACTED}\2",
    ),
)


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    """Sustituye en el mensaje final cualquier valor sensible reconocible."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


def configure_logging(level: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"redact": {"()": RedactingFilter}},
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["redact"],
                },
            },
            "root": {"level": level, "handlers": ["console"]},
            "loggers": {
                # Uvicorn trae sus propios handlers; se redirigen al nuestro
                # para que también pasen por el filtro de redacción.
                "uvicorn": {"level": level, "handlers": ["console"], "propagate": False},
                "uvicorn.error": {"level": level, "handlers": ["console"], "propagate": False},
                "uvicorn.access": {"level": level, "handlers": ["console"], "propagate": False},
            },
        }
    )
