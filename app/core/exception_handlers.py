from fastapi import FastAPI

from app.core.exceptions import (
    create_exception_handler,
    ServerError,
    AuthenticationError,
    UserExistsError,
    InvalidOtpError,
    UserNotFoundError,
    CredentialError,
    AuthorizationError,
    ServiceUnavailable,
    DocumentNotFoundError
)


class ExceptionHandler:
    def __init__(self, app: FastAPI):
        self._app = app

    def add_handlers(self):
        self._app.add_exception_handler(
            ServerError,
            create_exception_handler(
                status_code=500,
                initial_detail={
                    "status": "error",
                    "message": "Oops! Something went wrong.",
                },
            ),
        )

        self._app.add_exception_handler(
            ServiceUnavailable,
            create_exception_handler(
                status_code=503,
                initial_detail={
                    "status": "error",
                    "message": "Service unavailble! Try again after five minutes",
                },
            ),
        )

        self._app.add_exception_handler(
            AuthenticationError,
            create_exception_handler(
                status_code=401,
                initial_detail={
                    "status": "error",
                    "message": "User not authenticated.",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=AuthorizationError,
            handler=create_exception_handler(
                status_code=403,
                initial_detail={
                    "status": "error",
                    "message": "User is not authorized to make the requested action",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=UserExistsError,
            handler=create_exception_handler(
                status_code=409,
                initial_detail={
                    "status": "error",
                    "message": "User already exists with the provided email {user_email}",
                },
            ),
        )

        self._app.add_exception_handler(
            InvalidOtpError,
            create_exception_handler(
                initial_detail={
                    "status": "error",
                    "message": "Invalid otp received",
                },
                status_code=400,
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=UserNotFoundError,
            handler=create_exception_handler(
                status_code=404,
                initial_detail={
                    "status": "error",
                    "message": "User not found with email {user_email}",
                },
            ),
        )

        self._app.add_exception_handler(
            CredentialError,
            create_exception_handler(
                initial_detail={
                    "status": "error",
                    "message": "Invalid credentials!",
                },
                status_code=400,
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=DocumentNotFoundError,
            handler=create_exception_handler(
                status_code=404,
                initial_detail={
                    "status": "error",
                    "message": "Document not found with id {doc_id}",
                },
            ),
        )
