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
            ERROR_CODES["UNSUPPORTED_CONTEXT_MODE"],
            f"{context_mode} is not supported for the MVP read path.",
            http_status=400,
            category="VALIDATION",
            target="contextMode",
            details={"contextMode": context_mode, "supportedModes": MVP_CONTEXT_MODES},
        )

    return context_mode


def is_mvp_context_mode(context_mode):
    return context_mode in MVP_CONTEXT_MODES
