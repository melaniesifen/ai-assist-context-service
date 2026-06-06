ERROR_CODES = {
    "VALIDATION_ERROR": "VALIDATION_ERROR",
    "CONTEXT_MODE_UNSUPPORTED": "UNSUPPORTED_CONTEXT_MODE",
    "UNSUPPORTED_CONTEXT_MODE": "UNSUPPORTED_CONTEXT_MODE",
    "CONSENT_REQUIRED": "CONSENT_REQUIRED",
    "CONSENT_DENIED": "CONSENT_DENIED",
    "CONTEXT_TOO_LARGE": "CONTEXT_TOO_LARGE",
    "CONNECTOR_VERIFICATION_REQUIRED": "CONNECTOR_VERIFICATION_REQUIRED",
}


class ContextServiceError(Exception):
    def __init__(
        self,
        code,
        message,
        *,
        http_status=400,
        details=None,
        retryable=False,
        category=None,
        target=None,
    ):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.details = details or {}
        self.retryable = retryable
        self.category = category
        self.target = target


def context_error(code, message, **options):
    return ContextServiceError(code, message, **options)


def is_context_service_error(error):
    return isinstance(error, ContextServiceError)
