"""Standard error envelope with machine-readable codes + degradedMode (spec §4.3)."""

from __future__ import annotations


class MediSenseError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        detail: dict | None = None,
        degraded: bool = False,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        self.degraded = degraded
        super().__init__(message)


class AuthError(MediSenseError):
    def __init__(self, message: str = "Not authenticated") -> None:
        super().__init__("unauthenticated", message, status_code=401)


class ForbiddenError(MediSenseError):
    def __init__(self, message: str = "Insufficient role for this action") -> None:
        super().__init__("forbidden", message, status_code=403)


class NotFoundError(MediSenseError):
    def __init__(self, what: str = "resource") -> None:
        super().__init__("not_found", f"{what} not found", status_code=404)


class SafetyBlockError(MediSenseError):
    """A hard safety rule blocked an action (e.g. contraindication without override)."""

    def __init__(self, message: str, detail: dict | None = None) -> None:
        super().__init__("safety_block", message, status_code=409, detail=detail)
