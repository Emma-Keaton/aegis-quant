from typing import Optional, Any


class AegisQuantError(Exception):
    """Base exception for Aegis Quant"""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(AegisQuantError):
    def __init__(self, message: str = "Authentication failed", details: Optional[dict] = None):
        super().__init__(message, "AUTH_ERROR", 401, details)


class AuthorizationError(AegisQuantError):
    def __init__(self, message: str = "Not authorized", details: Optional[dict] = None):
        super().__init__(message, "AUTHORIZATION_ERROR", 403, details)


class ValidationError(AegisQuantError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "VALIDATION_ERROR", 400, details)


class NotFoundError(AegisQuantError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            f"{resource} not found: {identifier}",
            "NOT_FOUND",
            404,
            {"resource": resource, "identifier": identifier}
        )


class TelegramAuthError(AegisQuantError):
    def __init__(self, message: str):
        super().__init__(message, "TELEGRAM_AUTH_ERROR", 403)


class ExchangeError(AegisQuantError):
    def __init__(self, message: str, code: str = "EXCHANGE_ERROR", details: Optional[dict] = None):
        super().__init__(message, code, 502, details)


class InsufficientFundsError(AegisQuantError):
    def __init__(self, message: str = "Insufficient funds", details: Optional[dict] = None):
        super().__init__(message, "INSUFFICIENT_FUNDS", 400, details)


class RiskLimitExceededError(AegisQuantError):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, "RISK_LIMIT_EXCEEDED", 400, details)


class KronosError(AegisQuantError):
    def __init__(self, message: str, code: str = "KRONOS_ERROR", details: Optional[dict] = None):
        super().__init__(message, code, 503, details)


class GeminiError(AegisQuantError):
    def __init__(self, message: str, code: str = "GEMINI_ERROR", details: Optional[dict] = None):
        super().__init__(message, code, 503, details)


class EngineError(AegisQuantError):
    def __init__(self, engine: str, message: str, details: Optional[dict] = None):
        super().__init__(message, f"{engine.upper()}_ENGINE_ERROR", 500, {"engine": engine, **(details or {})})