from __future__ import annotations

import uuid
from typing import Any


class BaseError(Exception):
    def __init__(
        self,
        message: str = "",
        *,
        error_code: str = "UNKNOWN_ERROR",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        http_status: int = 500,
        cause: BaseException | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.error_code = error_code
        self.details = details or {}
        self.retryable = retryable
        self.http_status = http_status
        self.trace_id = trace_id or str(uuid.uuid4())

        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause


class ApplicationError(BaseError):
    def __init__(
        self,
        message: str = "",
        *,
        error_code: str = "APPLICATION_ERROR",
        details: dict[str, Any] | None = None,
        http_status: int = 500,
        cause: BaseException | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            retryable=False,
            http_status=http_status,
            cause=cause,
            trace_id=trace_id,
        )


class ConfigurationError(ApplicationError):
    def __init__(
        self,
        message: str = "",
        *,
        field: str = "",
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="CONFIGURATION_ERROR",
            details={**(details or {}), "field": field},
            http_status=500,
            trace_id=trace_id,
        )


class DependencyError(ApplicationError):
    def __init__(
        self,
        message: str = "",
        *,
        dependency_name: str = "",
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="DEPENDENCY_ERROR",
            details={**(details or {}), "dependency": dependency_name},
            http_status=500,
            trace_id=trace_id,
        )


class DomainError(BaseError):
    def __init__(
        self,
        message: str = "",
        *,
        error_code: str = "DOMAIN_ERROR",
        details: dict[str, Any] | None = None,
        http_status: int = 400,
        cause: BaseException | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            retryable=False,
            http_status=http_status,
            cause=cause,
            trace_id=trace_id,
        )


class ValidationError(DomainError):
    def __init__(
        self,
        message: str = "",
        *,
        field: str = "",
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            details={**(details or {}), "field": field},
            http_status=422,
            trace_id=trace_id,
        )


class NotFoundError(DomainError):
    def __init__(
        self,
        message: str = "",
        *,
        resource_type: str = "",
        resource_id: str = "",
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="NOT_FOUND",
            details={
                **(details or {}),
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
            http_status=404,
            trace_id=trace_id,
        )


class ConflictError(DomainError):
    def __init__(
        self,
        message: str = "",
        *,
        error_code: str = "CONFLICT",
        details: dict[str, Any] | None = None,
        http_status: int = 409,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            http_status=http_status,
            trace_id=trace_id,
        )


class UnauthorizedError(DomainError):
    def __init__(
        self,
        message: str = "",
        *,
        error_code: str = "UNAUTHORIZED",
        details: dict[str, Any] | None = None,
        http_status: int = 401,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            http_status=http_status,
            trace_id=trace_id,
        )


class InfrastructureError(BaseError):
    def __init__(
        self,
        message: str = "",
        *,
        error_code: str = "INFRASTRUCTURE_ERROR",
        details: dict[str, Any] | None = None,
        retryable: bool = True,
        http_status: int = 503,
        cause: BaseException | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            retryable=retryable,
            http_status=http_status,
            cause=cause,
            trace_id=trace_id,
        )


class ExternalServiceError(InfrastructureError):
    def __init__(
        self,
        message: str = "",
        *,
        service_name: str = "",
        details: dict[str, Any] | None = None,
        retryable: bool = True,
        http_status: int = 502,
        cause: BaseException | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={**(details or {}), "service": service_name},
            retryable=retryable,
            http_status=http_status,
            cause=cause,
            trace_id=trace_id,
        )


class TimeoutError(InfrastructureError):
    def __init__(
        self,
        message: str = "",
        *,
        timeout_seconds: float = 0.0,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="TIMEOUT",
            details={**(details or {}), "timeout_seconds": timeout_seconds},
            retryable=True,
            http_status=504,
            trace_id=trace_id,
        )
