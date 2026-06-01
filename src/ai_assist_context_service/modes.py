from .constants import CONTEXT_MODES, MVP_CONTEXT_MODES
from .errors import ERROR_CODES, context_error


def validate_context_mode(context_mode):
    allowed_modes = tuple(CONTEXT_MODES.values())
    if context_mode not in allowed_modes:
        raise context_error(
            ERROR_CODES["VALIDATION_ERROR"],
            "contextMode is not recognized",
            details={"field": "contextMode", "allowedModes": allowed_modes},
        )

    if context_mode not in MVP_CONTEXT_MODES:
        raise context_error(
            ERROR_CODES["CONTEXT_MODE_UNSUPPORTED"],
            "contextMode is not supported in MVP",
            http_status=422,
            details={"contextMode": context_mode, "supportedModes": MVP_CONTEXT_MODES},
        )

    return context_mode


def is_mvp_context_mode(context_mode):
    return context_mode in MVP_CONTEXT_MODES
