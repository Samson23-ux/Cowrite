from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    pass


class ServerError(AppException):
    """Internal Server error."""

    pass


class ServiceUnavailable(AppException):
    """Service unavailable temporarily"""

    pass


class MaxRetriesError(AppException):
    """Maximum retries exceeded"""

    pass


class AuthenticationError(AppException):
    """User not authenticated."""

    pass


class AuthorizationError(AppException):
    """User not authorized"""

    pass


class EmailExistsError(AppException):
    """Email already exists"""

    def __init__(self, user_email: str):
        self.user_email = user_email


class NameExistsError(AppException):
    """Display name already exists"""

    def __init__(self, display_name: str):
        self.display_name = display_name


class UserNotFoundError(AppException):
    """User not found"""

    def __init__(self, user_email: str):
        self.user_email = user_email


class DocumentNotFoundError(AppException):
    """Dcoument not found"""

    def __init__(self, doc_id: str):
        self.doc_id = doc_id


class InvalidOtpError(AppException):
    """Invalid otp received"""

    pass


class CredentialError(AppException):
    """wrong credentials provided"""

    pass


def create_exception_handler(
    status_code: int, initial_detail: dict
) -> callable[[Request, AppException], JSONResponse]:
    async def exception_handler(request: Request, exc: AppException):
        message: str = initial_detail.get("message")
        initial_detail["message"] = message.format(**exc.__dict__)

        return JSONResponse(content=initial_detail, status_code=status_code)

    return exception_handler
