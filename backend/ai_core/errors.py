"""Errors the AI core reports to the designer, in the error shape from AGENTS.md."""

from fastapi.responses import JSONResponse


class AiCoreError(Exception):
    """A failure with a message written for the designer."""

    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status,
            content={"error": {"code": self.code, "message": self.message}},
        )
