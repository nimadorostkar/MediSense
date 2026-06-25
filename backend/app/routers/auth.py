"""Auth endpoints for the web UI (spec §8).

`POST /api/auth/login` issues a bearer token the frontend stores and sends on
every request. In DEV_AUTH mode it mints a locally-signed dev token (no hospital
IdP needed); the role is inferred from the email prefix so RBAC can be exercised
end-to-end (nurse@…, pharmacist@…, admin@…, safety@…, it@… → that role; else
physician). In production (DEV_AUTH=false) the SPA performs the OIDC
authorization-code flow against the hospital IdP and this endpoint is disabled.
"""

from __future__ import annotations

import re

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.deps import CurrentUser, SessionDep
from app.errors import AuthError
from app.security.audit import record_event
from app.security.oidc import User, mint_dev_token
from app.security.rbac import Role

router = APIRouter(prefix="/api/auth", tags=["auth"])

_ROLE_PREFIX = {
    "nurse": Role.NURSE,
    "pharmacist": Role.PHARMACIST,
    "pharm": Role.PHARMACIST,
    "admin": Role.ADMIN,
    "safety": Role.SAFETY,
    "it": Role.IT,
}


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v.strip()):
            raise ValueError("invalid email")
        return v.strip()


class LoginResponse(BaseModel):
    token: str
    user: dict


def _infer(email: str) -> tuple[str, str]:
    """Return (display_name, role) from the email local-part."""
    local = email.split("@", 1)[0]
    role = Role.PHYSICIAN
    for prefix, r in _ROLE_PREFIX.items():
        if local.lower().startswith(prefix):
            role = r
            break
    name = local.replace(".", " ").replace("_", " ").title()
    if role == Role.PHYSICIAN and not name.lower().startswith("dr"):
        name = f"Dr {name}"
    return name, str(role)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, session: SessionDep) -> LoginResponse:
    if not settings.dev_auth:
        raise AuthError(
            "Direct login is disabled — authenticate via the hospital identity "
            "provider (OIDC authorization-code flow)."
        )
    name, role = _infer(str(body.email))
    token = mint_dev_token(sub=str(body.email), name=name, role=role)
    await record_event(
        session,
        actor=name,
        role=role,
        action="auth.login",
        target=f"user:{body.email}",
        detail={"mode": "dev"},
    )
    await session.commit()
    return LoginResponse(token=token, user={"email": str(body.email), "name": name, "role": role})


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    return {"name": user.name, "role": user.role, "sub": user.sub, "region": user.region}


@router.get("/config")
async def auth_config() -> dict:
    """Lets the SPA learn whether to use dev login or redirect to the IdP."""
    return {
        "devAuth": settings.dev_auth,
        "oidcIssuer": settings.oidc_issuer,
        "oidcAudience": settings.oidc_audience,
    }


__all__ = ["router", "User"]
