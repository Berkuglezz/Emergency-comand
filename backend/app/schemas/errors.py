from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Cuerpo de los errores de la API. `detail` es un código, no un texto."""

    detail: str
