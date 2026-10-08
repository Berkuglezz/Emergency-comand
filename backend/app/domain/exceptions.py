"""Excepciones de dominio.

Los servicios lanzan estas excepciones y no conocen HTTP. La capa API
(`app.api.errors`) las traduce a respuestas HTTP. Cada excepción expone un
`code` estable que el frontend traduce; nunca un texto para el usuario.
"""


class DomainError(Exception):
    code: str = "domain_error"

    def __init__(self, code: str | None = None) -> None:
        if code is not None:
            self.code = code
        super().__init__(self.code)


class NotFoundError(DomainError):
    code = "not_found"


class ConflictError(DomainError):
    code = "conflict"


class AuthenticationError(DomainError):
    """Credenciales o tokens ausentes o inválidos. Códigos usados:
    `not_authenticated`, `invalid_token`, `invalid_credentials`,
    `invalid_refresh_token`, `refresh_token_reused`, `refresh_token_rotated`."""

    code = "not_authenticated"


class PermissionDeniedError(DomainError):
    code = "permission_denied"


class InvalidInputError(DomainError):
    """Entrada válida en forma pero no según las reglas de dominio
    (p. ej. `details` que no cumple el esquema del tipo)."""

    code = "invalid_input"
